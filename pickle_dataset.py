#!/usr/bin/python3

from six.moves import cPickle
import cv2
import fnmatch
import math
import numpy as np
import os
import pandas as pd
import sys

# Directory of dataset to use
TRAIN_DIR = "dataset_sample"
# TRAIN_DIR = "boneage-training-dataset"

# Use the first N images, If it is -1 using all dataset
CUT_DATASET = 7200

# Turn saving renders feature on/off
SAVE_RENDERS = False

# Create intermediate images in separate folders for debugger.
# mask, cut_hand, delete_object, render
SAVE_IMAGE_FOR_DEBUGGER = False

# Extracting hands from images and using that new dataset.
# Simple dataset is correct, I am verifying the original.
EXTRACTING_HANDS = True

# Turn rotate image on/off
ROTATE_IMAGE = True

# For this problem the validation and test data provided by the concerned authority did not have labels,
# so the training data was split into train, test and validation sets
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

train_dir = os.path.join(__location__, TRAIN_DIR)

img_file = ""

df = pd.read_csv(os.path.join(train_dir, "boneage-training-dataset.csv"))
a = df.values
m = a.shape[0]


# Show the images
def writeImage(path, image, force=False):
    if SAVE_IMAGE_FOR_DEBUGGER or force:
        cv2.imwrite(os.path.join(__location__, TRAIN_DIR, path, img_file), image)


# Auto adjust levels colors
# We order the colors of the image with their frequency and
# obtain the accumulated one, then we obtain the colors that
# accumulate 2.5% and 99.4% of the frequency.
def histogramsLevelFix(img):
    # This function is only prepared for images in scale of gripes
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Find the acceptable limits of the intensity histogram
    min_color, max_color = np.percentile(img, (2.5, 99.4))
    min_color = int(min_color)
    max_color = int(max_color)

    # To improve the preform we created a color palette with the new values
    colors_palette = []
    # Auxiliary calculation, avoid doing calculations within the 'for'
    dif_color = 255 / (max_color - min_color)
    for color in range(256):
        if color <= min_color:
            colors_palette.append(0)
        elif color >= max_color:
            colors_palette.append(255)
        else:
            colors_palette.append(int(round((color - min_color) * dif_color)))

    # We paint the image with the new color palette
    height, width = img.shape
    for y in range(0, height):
        for x in range(0, width):
            color = img[y, x]
            img[y, x] = colors_palette[color]

    writeImage("histograms_level_fix", np.hstack([img]))  # show the images ===========

    return img


# Cut the hand of the image
# Look for the largest objects and create a mask, with that new mask
# is applied to the original and cut out.
def cutHand(image):
    image_copy = image.copy()

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    img = clahe.apply(image)

    img = cv2.medianBlur(img, 5)
    th2 = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2
    )
    th3 = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    thresh = cv2.bitwise_not(th3, th2)
    thresh = cv2.GaussianBlur(thresh, (5, 5), 0)

    (_, contours, _) = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # I guess the largest object is the hand or the only object in the image.
    largest_object_index = 0
    for i, cnt in enumerate(contours):
        if cv2.contourArea(contours[largest_object_index]) < cv2.contourArea(cnt):
            largest_object_index = i

    # create bounding rectangle around the contour (can skip below two lines)
    [x, y, w, h] = cv2.boundingRect(contours[largest_object_index])
    # White background below the largest object
    cv2.rectangle(image, (x, y), (x + w, y + h), (255), -1)

    cv2.drawContours(
        image,  # image,
        contours,  # objects
        largest_object_index,  # índice de objeto (-1, todos)
        (255),  # color
        -1,  # tamaño del borde (-1, pintar adentro)
    )

    # Trim that object of mask and image
    mask = image[y: y + h, x: x + w]
    image_cut = image_copy[y: y + h, x: x + w]

    # Apply mask
    image_cut = cv2.bitwise_and(image_cut, image_cut, mask=mask)

    writeImage("cut_hand", np.hstack([image_cut]))  # show the images ===========

    return image_cut


def rotateImage(imageToRotate):
    edges = cv2.Canny(imageToRotate, 50, 150, apertureSize=3)
    # Obtener una línea de la imágen
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 180)
    if not (lines is None) and len(lines) >= 1:
        for i in range(1):
            for rho, theta in lines[i]:
                a = np.cos(theta)
                b = np.sin(theta)
                x0 = a * rho
                y0 = b * rho
                x1 = int(x0 + 1000 * (-b))
                y1 = int(y0 + 1000 * (a))
                x2 = int(x0 - 1000 * (-b))
                y2 = int(y0 - 1000 * (a))
                # cv2.line(imageToRotate, (x1, y1), (x2, y2), (0, 0, 255), 2)
                angle = math.atan2(y1 - y2, x1 - x2)
                angleDegree = (angle * 180) / math.pi
            if angleDegree < 0:
                angleDegree = angleDegree + 360
            if angleDegree >= 0 and angleDegree < 45:
                angleToSubtract = 0
            elif angleDegree >= 45 and angleDegree < 135:
                angleToSubtract = 90
            elif angleDegree >= 135 and angleDegree < 225:
                angleToSubtract = 180
            elif angleDegree >= 225 and angleDegree < 315:
                angleToSubtract = 270
            else:
                angleToSubtract = 0
            angleToRotate = angleDegree - angleToSubtract
            num_rows, num_cols = imageToRotate.shape[:2]
            rotation_matrix = cv2.getRotationMatrix2D(
                (num_cols / 2, num_rows / 2), angleToRotate, 1
            )
            imageToRotate = cv2.warpAffine(
                imageToRotate, rotation_matrix, (num_cols, num_rows)
            )
    return imageToRotate


# Show a progress bar
def updateProgress(progress, tick="", total="", status="Loading..."):
    lineLength = 80
    barLength = 23
    if isinstance(progress, int):
        progress = float(progress)
    if progress < 0:
        progress = 0
        status = "Waiting...\r"
    if progress >= 1:
        progress = 1
        status = "Completed loading data\r\n"
    block = int(round(barLength * progress))
    line = str("\rImage: {0}/{1} [{2}] {3}% {4}").format(
        tick,
        total,
        str(("#" * block)) + str("." * (barLength - block)),
        round(progress * 100, 1),
        status,
    )
    emptyBlock = lineLength - len(line)
    emptyBlock = " " * emptyBlock if emptyBlock > 0 else ""
    sys.stdout.write(line + emptyBlock)
    sys.stdout.flush()


def loadDataSet(files=[]):
    X_train = []
    y_age = []
    y_gender = []

    total_file = len(files)
    for i in range(total_file):
        global img_file
        img_file = files[i]

        # Update the progress bar
        progress = float(i / total_file), (i + 1)
        updateProgress(progress[0], progress[1], total_file, img_file)

        y_age.append(df.boneage[df.id == int(img_file[:-4])].tolist()[0])
        a = df.male[df.id == int(img_file[:-4])].tolist()[0]
        if a:
            y_gender.append(1)
        else:
            y_gender.append(0)

        # Read a image
        img_path = os.path.join(train_dir, img_file)
        img = cv2.imread(img_path)

        # Adjust color levels
        img = histogramsLevelFix(img)

        if EXTRACTING_HANDS:
            # Trim the hand of the image
            img = cutHand(img)

        if ROTATE_IMAGE:
            # Rotate hands
            img = rotateImage(img)

        # ====================== show the images ================================
        if SAVE_IMAGE_FOR_DEBUGGER or SAVE_RENDERS:
            cv2.imwrite(os.path.join(__location__, TRAIN_DIR, "render", img_file), img)

        # Resize the images
        img = cv2.resize(img, (224, 224))
        # Return to original colors
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        x = np.asarray(img, dtype=np.uint8)
        X_train.append(x)

    updateProgress(1, total_file, total_file, img_file)

    return X_train, y_age, y_gender


# Save dataset
def saveDataSet(X_train, y_age, y_gender):
    print("\nSaving data...")
    # Save data
    train_pkl = open("data.pkl", "wb")
    cPickle.dump(X_train, train_pkl, protocol=cPickle.HIGHEST_PROTOCOL)
    train_pkl.close()

    train_age_pkl = open("data_age.pkl", "wb")
    cPickle.dump(y_age, train_age_pkl, protocol=cPickle.HIGHEST_PROTOCOL)
    train_age_pkl.close()

    train_gender_pkl = open("data_gender.pkl", "wb")
    cPickle.dump(y_gender, train_gender_pkl, protocol=cPickle.HIGHEST_PROTOCOL)
    train_gender_pkl.close()
    print("\nCompleted saved data")


# list all the image files and randomly unravel them,
# in each case you take the first N from the unordered list
def getFiles():
    # file names on train_dir
    files = os.listdir(train_dir)
    # filter image files
    files = [f for f in files if fnmatch.fnmatch(f, "*.png")]
    # Sort randomly
    np.random.shuffle(files)
    # Cut list of file
    if CUT_DATASET > 0:
        files = files[:CUT_DATASET]
    return files


# Create the directories to save the images
def checkPath():
    if SAVE_IMAGE_FOR_DEBUGGER:
        for folder in ["histograms_level_fix", "cut_hand", "render", "mask"]:
            if not os.path.exists(os.path.join(__location__, TRAIN_DIR, folder)):
                os.makedirs(os.path.join(__location__, TRAIN_DIR, folder))
    if SAVE_RENDERS:
        if not os.path.exists(os.path.join(__location__, TRAIN_DIR, "render")):
            os.makedirs(os.path.join(__location__, TRAIN_DIR, "render"))


# Como vamos a usar multi procesos uno por core.
# Los procesos hijos cargan el mismo código.
# Este if permite que solo se ejecute lo que sigue si es llamado
# como proceso raíz.
if __name__ == "__main__":
    checkPath()

    files = getFiles()
    (X_train, y_age, y_gender) = loadDataSet(files)
    saveDataSet(X_train, y_age, y_gender)
