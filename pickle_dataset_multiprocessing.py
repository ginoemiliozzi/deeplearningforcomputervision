#!/usr/bin/python3

from multiprocessing import Process
import multiprocessing
import os
import pickle_dataset as pDataset
import platform

# For this problem the validation and test data provided by the concerned authority did not have labels,
# so the training data was split into train, test and validation sets
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

# Usado en caso de usar multiples core
output = multiprocessing.Queue()


def mpStart(files, output):
    output.put(pDataset.loadDataSet(files))


if __name__ == "__main__":
    # Create the directories to save the images
    pDataset.checkPath()

    files = pDataset.getFiles()
    total_file = len(files)
    print("Image total:", total_file)

    num_processes = multiprocessing.cpu_count()
    if platform.system() == "Linux" and num_processes > 1:
        processes = []

        lot_size = int(total_file / num_processes)

        for x in range(1, num_processes + 1):
            if x < num_processes:
                lot_img = files[(x - 1) * lot_size: ((x - 1) * lot_size) + lot_size]
            else:
                lot_img = files[(x - 1) * lot_size:]
            processes.append(Process(target=mpStart, args=(lot_img, output)))

        if len(processes) > 0:
            print("Loading data set...")
            for p in processes:
                p.start()

            result = []
            for x in range(num_processes):
                result.append(output.get(True))

            for p in processes:
                p.join()

            X_train = []
            y_age = []
            y_gender = []
            for mp_X_train, mp_y_age, mp_y_gender in result:
                X_train = X_train + mp_X_train
                y_age = y_age + mp_y_age
                y_gender = y_gender + mp_y_gender
            print("Image processed:", len(X_train))
            pDataset.saveDataSet(X_train, y_age, y_gender)
    else:
        print("No podemos dividir la cargan en distintos procesadores")
        exit(0)
