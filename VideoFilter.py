import os, sys
import ffmpeg
from multiprocessing import Pool, cpu_count
import cv2
import numpy as np


def create_folder(wk_path):
    try:
        os.mkdir(wk_path)
    except Exception  as e:
        print(str(e))


def concat_vh(list_2d):
    # return final image
    return cv2.vconcat([cv2.hconcat(list_h)
                        for list_h in list_2d])

cache_path = "_video_filter"

def generate_thubnail_idx(input_data):
    (in_filename, time_offset) = input_data
    probe = ffmpeg.probe(in_filename)
    time = float(probe['streams'][0]['duration']) // 5
    width = probe['streams'][0]['width']

    for idx in [1, 2, 3, 4]:
        img_path = os.path.join(cache_path, "{}_{}.jpg".format(os.path.basename(in_filename), idx))
        if os.path.exists(img_path):
            os.remove(img_path)
        try:
            (
                ffmpeg
                .input(in_filename, ss=time*idx + time_offset)
                .filter('scale', width, -1)
                .output(img_path, vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            print(e.stderr.decode(), file=sys.stderr)
            sys.exit(1)

    return None

def prepare_thumbnail(in_filename_list):
    work_datas = [[in_filename, 0] for in_filename in in_filename_list]
    p = Pool(cpu_count())
    p.map(generate_thubnail_idx, work_datas)


def generate_thumbnail(in_filename_list, delete_folder):
    for idx, in_filename in enumerate(in_filename_list):
        size_in_gbyte = os.path.getsize(in_filename) / 1024 / 1024 / 1024
        text_label = "[ {}/{} ] {:.4f}GB press D to delete, X to stop, R to refresh, else to skip".format(idx+1, len(in_filename_list), size_in_gbyte)

        offset = 0
        while True:
            image_file_path_list = [os.path.join(cache_path, "{}_{}.jpg".format(os.path.basename(in_filename), idx)) for idx in [1, 2, 3, 4]]
            try:
                img_list = [cv2.imdecode(np.fromfile(fp,dtype=np.uint8),-1) for fp in image_file_path_list]
            except Exception as e:
                print(str(e))
                break

            img_list_2d = [[img_list[0],img_list[1]],
                           [img_list[2],img_list[3]]]
            img1 = concat_vh(img_list_2d)
            cv2.putText(img1, text_label, org=(10,30), fontFace= cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.7, color=(255,128,128), thickness=1, lineType=cv2.LINE_AA)

            window_name = os.path.basename(in_filename)
            window_name = window_name.encode("gbk").decode('UTF-8', errors='ignore')
            # cv2.namedWindow(window_name)
            cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
            cv2.moveWindow(window_name, 200, 200)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            src_size_h, src_size_w = (img1.shape[0], img1.shape[1]) # height & width
            tgt_size_w, tgt_size_h = (2560, 1440) # width & height
            img_bg = np.zeros([tgt_size_h, tgt_size_w, 3], dtype=np.uint8)
            if src_size_h / src_size_w > tgt_size_h / tgt_size_w:
                tgt_size_w = tgt_size_h * src_size_w / src_size_h
            else:
                tgt_size_h = tgt_size_w * src_size_h / src_size_w

            tgt_size_tuple = (int(tgt_size_w), int(tgt_size_h))
            cv2.resizeWindow(window_name, *tgt_size_tuple)

            scaled_image = cv2.resize(img1, tgt_size_tuple)
            cv2.imshow(window_name, scaled_image)

            pressed = cv2.waitKey(0)
            cv2.destroyAllWindows()
            if chr(pressed & 255) in 'rR':
                offset += 90
                generate_thubnail_idx((in_filename, offset))
            else:
                if chr(pressed & 255) in 'dD':
                    os.rename(in_filename, os.path.join(delete_folder, os.path.basename(in_filename)))
                    print(in_filename, " delete")
                elif chr(pressed & 255) in 'xX':
                    exit(0)
                break


def glob_folders(top_path):
    if not os.access(top_path, os.R_OK):
        return
    create_folder(cache_path)
    delete_folder = os.path.join(top_path, cache_path)
    create_folder(delete_folder)

    files_to_check = []
    for entry in os.scandir(top_path):
        if os.access(entry, os.R_OK) and os.path.isfile(entry.path):
            print(entry.path)
            if os.path.splitext(os.path.basename(entry.path))[1] == ".mp4":
                files_to_check.append(entry.path)

    prepare_thumbnail(files_to_check)
    generate_thumbnail(files_to_check, delete_folder)

def filt_video(top_path):
    for entry in os.scandir(top_path):
        if os.access(entry, os.R_OK) and os.path.isfile(entry.path):
            if os.path.splitext(os.path.basename(entry.path))[1] == ".mp4":
                pass

if __name__ == "__main__":
    root_dir = r"U:\col_atv\20220706\big"
    glob_folders(root_dir)