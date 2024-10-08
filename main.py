from typing import Optional
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
import torch
import cv2
from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity as ssim

app = FastAPI()

# تحميل النموذج المدرب مسبقاً من YOLOv5
model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)

# تحميل نماذج اكتشاف الوجه والعمر
faceProto = "modelNweight/opencv_face_detector.pbtxt"
faceModel = "modelNweight/opencv_face_detector_uint8.pb"
ageProto = "modelNweight/age_deploy.prototxt"
ageModel = "modelNweight/age_net.caffemodel"
MODEL_MEAN_VALUES = (78.4263377603, 87.7689143744, 114.895847746)
ageList = ['(0-2)', '(4-6)', '(8-12)', '(15-20)', '(25-32)', '(38-43)', '(48-53)', '(60-100)']

# تحميل الشبكات
ageNet = cv2.dnn.readNet(ageModel, ageProto)
faceNet = cv2.dnn.readNet(faceModel, faceProto)

padding = 20

def getFaceBox(net, frame, conf_threshold=0.7):
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), [104, 117, 123], True, False)
    net.setInput(blob)
    detections = net.forward()
    bboxes = []
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > conf_threshold:
            x1 = int(detections[0, 0, i, 3] * frameWidth)
            y1 = int(detections[0, 0, i, 4] * frameHeight)
            x2 = int(detections[0, 0, i, 5] * frameWidth)
            y2 = int(detections[0, 0, i, 6] * frameHeight)
            bboxes.append([x1, y1, x2, y2])
    return bboxes

def detect_age(frame, bbox):
    face = frame[max(0, bbox[1]-padding):min(bbox[3]+padding, frame.shape[0]-1),
                 max(0, bbox[0]-padding):min(bbox[2]+padding, frame.shape[1]-1)]
    blob = cv2.dnn.blobFromImage(face, 1.0, (227, 227), MODEL_MEAN_VALUES, swapRB=False)
    ageNet.setInput(blob)
    agePreds = ageNet.forward()
    return ageList[agePreds[0].argmax()]

def resize_image(image, size=(256, 256)):
    return cv2.resize(image, size)

def calculate_similarity(img1, img2):
    img1_resized = resize_image(img1)
    img2_resized = resize_image(img2)
    img1_gray = cv2.cvtColor(img1_resized, cv2.COLOR_BGR2GRAY)
    img2_gray = cv2.cvtColor(img2_resized, cv2.COLOR_BGR2GRAY)
    score, _ = ssim(img1_gray, img2_gray, full=True)
    return score

def compare_images(dict_in, dict_out):
    images_in = dict_in.get('child', [])
    images_out = dict_out.get('child', [])
    num_images_in = len(images_in)
    num_images_out = len(images_out)
    min_images = min(num_images_in, num_images_out)
    similarity_scores = []
    for i in range(min_images):
        img_in = images_in[i]
        img_out = images_out[i]
        similarity = calculate_similarity(img_in, img_out)
        similarity_scores.append(similarity)
        print(f"تشابه بين الصورة {i+1} في dict_in و الصورة {i+1} في dict_out: {similarity:.2f}")
    if num_images_in > num_images_out:
        for i in range(num_images_out, num_images_in):
            print(f"لا توجد صورة مقابلة للصورة {i+1} في dict_in في dict_out.")
    elif num_images_out > num_images_in:
        for i in range(num_images_in, num_images_out):
            print(f"لا توجد صورة مقابلة للصورة {i+1} في dict_out في dict_in.")
    threshold = 0.8
    found_similar = any(score > threshold for score in similarity_scores[:3])
    if found_similar:
        print("الطفل موجود مع أحد الوالدين.")
    else:
        print("تحذير: قد يكون الطفل مختطفاً.")

class ImagePair(BaseModel):
    image1: UploadFile
    image2: UploadFile

@app.post("/compare")
async def compare_images_endpoint(images: ImagePair):
    image1 = Image.open(images.image1.file)
    image2 = Image.open(images.image2.file)
    image1_cv = np.array(image1)
    image2_cv = np.array(image2)

    # يجب عليك تحويل الصور إلى التنسيق المناسب
    # ثم تنفيذ عملية المقارنة هنا

    # قم بتعبئة القيم الخاصة بالصور
    cropped_objects_dict_in = {"child": [image1_cv]}
    cropped_objects_dict_out = {"child": [image2_cv]}

    compare_images(cropped_objects_dict_in, cropped_objects_dict_out)

    return {"message": "Images compared successfully."}


# مسار للترحيب الأساسي
@app.get("/")
async def root():
    return {"message": "Hello World"}

# مسار لاستخدام الـ items
@app.get("/items/{item_id}")
def read_item(item_id: int, q: Optional[str] = None):
    return {"item_id": item_id, "q": q}
