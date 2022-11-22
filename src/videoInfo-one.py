import cv2
import glob
import os
import datetime
import requests
import json
import sys
import struct
from urllib.parse import urlencode


#==== 接口调用 ====
isDev = False
_devApi = 'https://app-crm-platform-dev.weddingee.com'
_prodApi = 'https://feixiong.halobear.com'
if (isDev):
    baseURL = _devApi
else:
    baseURL = _prodApi
_headers = {'Content-Type': 'application/json', 'x-halo-app': 'app-murong'}

isCheckOk = True   # 检查视频文件是否有效

# 获取需检测的订单信息
def api_get_order():
    try:
        post_headers = _headers.copy()
        url = baseURL + '/api/app-crm-api/v1/travel/order/cameraman'
        data = {}
        r = requests.get(url, headers=post_headers, data=json.dumps(data))
        # print(r.text)
        ret = json.loads(r.text)
    except Exception as e:
        print('error:', e)
        return None, {'info': '获取订单检测接口错误'}
    return ret['iRet'] == 1, ret

# 提交订单的视频时长信息
def api_post_order(orderData):
    # print('-> ', orderData)
    try:
        post_headers = _headers.copy()
        url = baseURL + '/api/app-crm-api/v1/travel/order/cameraman/original/duration'
        data = {'data': json.dumps(orderData)}
        r = requests.post(url, headers=post_headers, data=json.dumps(data))
        # print(r.text)
        ret = json.loads(r.text)
    except Exception as e:
        print('error:', e)
        return None, {'info': '提交订单检测接口错误'}
    return ret['iRet'] == 1, ret

#==== 获取本地视频信息 ====
isRootPath = False  #自动判断是否群晖服务器

def my_output(str):
    global isRootPath
    print(str)
    current_time = datetime.datetime.now()
    str = current_time.strftime('%Y-%m-%d %H:%M:%S ') + str + "\n"
    filename = 'output_info.txt'
    if (isRootPath):
        filename = '/volume1/wenjun/mypython/output_info.txt'        
    with open(filename, 'a') as f:
        f.write(str)
        f.close


# 获取视频时长
def video_duration(filename):
    is_ok = False
    duration = 0
    try:
        cap = cv2.VideoCapture(filename)
        if cap.isOpened():
            rate = cap.get(5)
            frame_num = cap.get(7)
            duration = frame_num / rate
            is_ok = True
            # 检查视频数据是否正常
            # save_name = filename.split('.')[0]
            for i in range(3):
                idx = 0
                # 开头
                if i == 0 and frame_num > 50:
                    idx = 20
                # 结尾
                elif i == 2 and frame_num > 50:
                    idx = frame_num - 20
                # 中间
                else:
                    idx = frame_num / 2
                if isCheckOk and is_ok and idx > 0:
                    cap.set(1, idx)
                    rval, frame = cap.read()
                    if rval:
                        is_ok = True
                        # pic_name = save_name + '_' + str(i) + '.jpg'
                        # cv2.imencode('.jpg', frame)[1].tofile(pic_name)
                    else:
                        is_ok = False
                        my_output('*** Error frame: %d, %d, %s'%(idx, frame_num, filename))
        else:
            my_output('*** Error open: %s'%(filename))
    except cv2.error as e:
        is_ok = False
        my_output('*** cv2.error: %s'%(e))
    except Exception as e:
        is_ok = False
        my_output('*** Exception: %s'%(e))

    cap.release()
    return is_ok, duration

# 获取目录下所有视频文件
def get_video_files(path):
    files = glob.glob(os.path.join(path,'**/*.MP4'), recursive=True)
    return files

# 获取一个订单目录的视频文件信息，匹配用户名
def get_order_video(path, userName = "", bInfo = True):
    # my_output(path)
    total = 0
    total_ok = 0
    total_size = 0
    total_duration = 0
    bCheckUser = len(userName) > 0
    min_file_size = 0 # 最小文件
    min_file_name = ''
    files = get_video_files(path)
    for file_name in files:
        # 忽略采访
        if (file_name.find('采访') >= 0):
            continue
        # 忽略航拍
        basename = os.path.basename(file_name)
        if (basename.find('DJI_') >= 0):
            continue
        # 包含用户名
        if (bCheckUser and file_name.find(userName) < 0):
            continue

        total += 1
        if (bInfo):
            size = os.stat(file_name).st_size
            is_ok, duration = video_duration(file_name)
            if is_ok:
                total_ok += 1
            total_size += size
            total_duration += duration
            if min_file_size < 1:
                min_file_size = size
                min_file_name = file_name
            elif size < min_file_size:
                min_file_size = size
                min_file_name = file_name
            if not is_ok or duration < 1:
                my_output('- %s, %d, %.2f, %s'%(file_name, size, duration, is_ok))

    total_size = total_size / 1024 / 1024
    avg_size = 0
    avg_duration = 0
    if (total > 0):
        avg_size = total_size / total
        avg_duration = total_duration / total
    my_output('--> num: %d, error: %d, total size: %.2f, avg size: %.2f, total duration: %.2f, avg duration: %.2f, min file: %s'%(total, total - total_ok, total_size, avg_size, total_duration, avg_duration, min_file_name))
    return total, total_duration, min_file_name

# 获取目录下的订单目录
def get_order_dirs(path, layer = 2):
    # 目录结构：2022年5月/0506-619218-亚龙湾喜来登酒店-崔皓源&冯楠茜
    dir_list = []
    allFiles = os.listdir(path)
    for file in allFiles:
        filePath = os.path.join(path, file)
        if os.path.isdir(filePath):
            # print('- ', filePath)
            if (layer == 2):
                sub_list = get_order_dirs(filePath, 1)
                dir_list.extend(sub_list)
            else:
                dir_list.append(filePath)
    return dir_list

# 获取指定目录下的所有二级目录
def get_local_dirs():
    global isRootPath
    if (os.getcwd() == '/root'):
        isRootPath = True
    my_output('---- %s, %s'%(sys.version, sys.path))
    my_output('---- Current Path: ' + os.getcwd())
    video_path = '/volume'
    # video_path = 'E:/temp-video/摄像数据测试/问题视频测试'
    # video_path = '/volume3/视频部3/摄像师上传3/2022年05月/5月2号-611603-大理俊媛全海景美宿-董宸&庄洁'
    # video_path = 'C:/Users/wenjun/Desktop/摄像师上传/2022年5月/5月2号-611603-大理俊媛全海景美宿-董宸&庄洁'
    # video_path = 'C:/Users/wenjun/Desktop/摄像师上传/2022年5月/0506-619218-亚龙湾喜来登酒店-崔皓源&冯楠茜'
    my_output('---- Video Path: ' + video_path)

    local_list = []
    try:
        local_list = get_order_dirs(video_path, 2)
    except FileNotFoundError as e:
        my_output('*** Error: %s'%(e))
    return local_list

# 从本地目录列表查找包含指定机会ID的目录
def find_local_order(localList, chanceId):
    for local in localList:
        if (local.find(chanceId) >= 0):
            return local
    return ''


#--- 获取视频的相机设备信息 --
def getDevInfo(devData):
    start = devData.find('manufacturer')
    s1 = devData.find('"', start)
    e1 = devData.find('"', s1+1)
    manufacturer = devData[s1+1:e1]
    start = devData.find('modelName')
    s1 = devData.find('"', start)
    e1 = devData.find('"', s1+1)
    modelName = devData[s1+1:e1]
    my_output('品牌: ' + manufacturer + ', 型号: ' + modelName)
    return manufacturer, modelName


def find_devinfo(video_file):
    manufacturer = ''
    modelName = ''
    fsize = os.path.getsize(video_file)
    with open(video_file,'rb') as f:
        # sony
        f.seek(fsize - 1800)
        datas = f.read(1780)
        # print(datas)
        start = datas.find(b'manufacturer')
        end = datas.find(b'serialNo')
        # print(start, '-', end)

        data = datas[start:end]
        f.close()
        strData = str(data, "utf-8")
        # print(strData)
        manufacturer, modelName = getDevInfo(strData)
    return manufacturer, modelName


#==== 订单检测处理 ====
def order_check():
    order_list = []
    # 获取需检测订单
    ret, resp = api_get_order()
    if ret:
        order_list = resp['data']['list']
    else:
        my_output('Err: ' + resp['info'])

    # 获取本地所有订单目录
    local_dir_list = get_local_dirs()
    
    # 遍历需检测订单列表
    for order in order_list:
        chanceId = str(order['chance_id'])
        order_path = find_local_order(local_dir_list, chanceId)
        my_output('--: ' + chanceId + ', ' + order_path)
        if (len(order_path) > 6):
            data = []
            order_data = {'id': order['id'], 'chance_id': order['chance_id'], 'record': []}
            for record in order['record']:
                my_output('-- ' + record['record_name'])
                # 超过1个机位需匹配人员姓名
                userName = ''
                if (len(order['record']) > 1):
                    userName = record['record_name']
                num, duration, min_file_name = get_order_video(order_path, userName, True)
                # 设备信息
                manufacturer, modelName = find_devinfo(min_file_name)
                # 提交数据
                record_data = {'id': record['id'], 'record_id': record['record_id'], 'record_name': record['record_name'], 'original_video_num':num, 'original_duration': duration}
                order_data['record'].append(record_data)
            # 提交订单的视频时长
            # data.append(order_data)
            # ret, resp = api_post_order(data)
            # my_output('-->> ' + resp['info'])

    my_output('---- done' + "\n")

#==== 检测一个订单 ====
def order_one():
    order_list = []
    user_list = ['AAA']
    if len(sys.argv) > 1:
        order_list.append(sys.argv[1])
        if len(sys.argv) > 2:
            user_list.append(sys.argv[2])
        if len(sys.argv) > 3:
            user_list.append(sys.argv[3])
    else:
        order_list = ['638668']
        user_list = ['AAA']

    # 获取本地所有订单目录
    local_dir_list = get_local_dirs()
    
    # 遍历需检测订单列表
    for chanceId in order_list:
        order_path = find_local_order(local_dir_list, chanceId)
        my_output('--: ' + chanceId + ', ' + order_path)
        if (len(order_path) > 6):
            data = []
            for user_name in user_list:
                my_output('-- ' + user_name)
                # 超过1个机位需匹配人员姓名
                userName = ''
                if (len(user_list) > 1):
                    userName = user_name
                num, duration, min_file_name = get_order_video(order_path, userName, True)
                # 设备信息
                manufacturer, modelName = find_devinfo(min_file_name)

    my_output('---- done' + "\n")


# 启动调用
order_one()
# get_video()
# api_get_order()
