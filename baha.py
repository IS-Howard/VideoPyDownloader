import requests
import browser_cookie3
import json
import random
from datetime import datetime
import re
import time
import os
import subprocess
from tqdm import trange
import shutil
from PyInquirer import prompt, Separator
import pickle

def RandomString(K):
    S = "abcdefghijklmnopqrstuvwxyz0123456789"
    return ''.join(random.choice(S) for i in range(K))

def getConfig():
    with open('config.txt', 'r') as file:
        contents = file.read()
        download_path_match = re.search(r'Download Path:\s*(.*)', contents)
        quality_match = re.search(r'Quality:\s*(\d+)', contents)

        # Extract the download path and quality if found
        if download_path_match:
            downloadPath = download_path_match.group(1)
        else:
            downloadPath = None

        if quality_match:
            Quality = quality_match.group(1)
        else:
            Quality = None

    return downloadPath, Quality

def checkbox(eps):
    questions = [
        {
            'type': 'checkbox',
            'message': '選擇要下載的(已預選全部)',
            'name': 'sns',
            'choices': [{'name':eps[i][1], 'checked':True} for i in range(len(eps))],
            'validate': lambda answer: 'You must choose at least one' \
                if len(answer) == 0 else True
        }
    ]
    answers = prompt(questions)
    sel = set(answers['sns'])
    sel_eps = []
    for i in range(len(eps)):
        if eps[i][1] in sel:
            sel_eps.append(eps[i][0])
    return sel_eps

class BahaRequest:

    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Referer': 'https://ani.gamer.com.tw/',
        'origin': 'https://ani.gamer.com.tw'
    }

    def baha_get_title(sn, ep=True):
        if sn.startswith("http"):
            sn = sn.split("=")[-1]
        headers = BahaRequest.headers
        response = requests.get("https://api.gamer.com.tw/mobile_app/anime/v2/video.php?sn="+sn, headers=headers)
        rx = re.compile(r'"title":"(.*?)"},"anime"')
        utitle = rx.findall(response.text)[0]
        title = json.loads('"%s"' %utitle)
        if not ep:
            return title.rsplit(" ",1)[0]
        return title
    
    def baha_parse_episodes(link):
        headers = BahaRequest.headers
        response = requests.get(link, headers=headers)
        return re.findall(r'"\?sn=(\d{5})">(\d+\.?\d?)<', response.text)

    def baha_link_validate(link):
        linktype = 0 # bad link
        if not link.startswith("http"):
            link = "https://ani.gamer.com.tw/animeVideo.php?sn="+link
            linktype = 1 # sn
        else: # full link
            if link.find("https://ani.gamer.com.tw/animeVideo.php?sn=")==-1:
                return 0
            linktype = 2

        headers = BahaRequest.headers
        response = requests.get(link, headers=headers)
        if response.text.find("目前無此動畫或動畫授權已到期！")!=-1:
            return 0
        return linktype

    def baha_set_session():
        ss = requests.Session()

        if os.path.isfile('./cookie.sav'):
            cookie_set = 2
        else:
            cookie_set = 1
        
        if cookie_set == 1:   # load from chrome
            try:
                cookies = browser_cookie3.chrome(domain_name='gamer.com')
                ss.cookies = cookies
                pickle.dump(requests.utils.dict_from_cookiejar(cookies), open('./cookie.sav',"wb"))
            except:
                print("Error when loading cookies, please make sure tuning off chrome first!")
                return None
        elif cookie_set == 2: # load request cookie file
            # cookies = pickle.load(open('./cookie.sav', "rb"))
            # for cookie in cookies:
            #     if 'httpOnly' in cookie:
            #         httpO = cookie.pop('httpOnly')
            #         cookie['rest'] = {'httpOnly': httpO}
            #     if 'expiry' in cookie:
            #         cookie['expires'] = cookie.pop('expiry')
            #     # ss.cookies.set(**cookie)
            #     ss.cookies.set(cookie['name'], cookie['value'], path=cookie['path'])
            ss.cookies = requests.utils.cookiejar_from_dict(pickle.load(open('./cookie.sav','rb')))
        return ss
            
    def baha_download_request(sn, tmpPath, downloadPath, Quality="720"):
        # path initialize
        tmpPath = tmpPath+'/tmp'+sn
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        # request config and cookie
        headers = BahaRequest.headers
        ss = BahaRequest.baha_set_session()
        if not ss:
            return

        #Get Title
        title = BahaRequest.baha_get_title(sn)
        print(title)

        #ID
        response = ss.get('https://ani.gamer.com.tw/ajax/getdeviceid.php?id=', headers=headers)
        load = json.loads(response.text)
        deviceID = load["deviceid"]

        #Access
        response = ss.get('https://ani.gamer.com.tw/ajax/token.php?adID=undefined&sn='+sn+ "&device="+deviceID+"&hash="+RandomString(12), headers=headers)
        if(response.text.find("error")!=-1):
            print(response.text)
            print("Access Fail")
            #remove tmp files
            shutil.rmtree(tmpPath)
            return

        #Get Ad
        response = ss.get('https://i2.bahamut.com.tw/JS/ad/animeVideo2.js?v='+datetime.now().strftime("%Y%m%d%H"), headers=headers)
        rx = re.compile(r"php\?id=([0-9]{6})")
        match = rx.findall(response.text)
        ad = match[0].replace("php?id=","")

        #Start Ad
        response = ss.get('https://ani.gamer.com.tw/ajax/videoCastcishu.php?sn='+sn+'&s='+ad, headers=headers)
        for i in range(30):
            print(f"\r{30-i}秒後跳過廣告", end='', flush=True)
            time.sleep(1)
        print("\n")

        #skip ad
        response = ss.get('https://ani.gamer.com.tw/ajax/videoCastcishu.php?sn='+sn+'&s='+ad+'&ad=end', headers=headers)

        #Get video m3u8 link
        response = ss.get('https://ani.gamer.com.tw/ajax/videoStart.php?sn='+sn, headers=headers)
        response = ss.get('https://ani.gamer.com.tw/ajax/m3u8.php?sn='+sn+'&device='+deviceID, headers=headers)
        load = json.loads(response.text)
        MUrl = load["src"]

        #Parse m3u8 list
        response = ss.get(MUrl, headers=headers)
        sr = response.text
        lines = sr.split('\n')
        Res = ''
        for line in lines:
            if line.startswith("#EXT-X-STREAM-INF"):
                q = line.split('x')[1].strip()
                if Quality == q:
                    nextLine = lines[lines.index(line) + 1]
                    Res = nextLine.split('?')[0].strip()
                    break
        if Res == '':
            print("Parse List Fail")
            #remove tmp files
            shutil.rmtree(tmpPath)
            return
        
        #Tmp saving (list, key, chunks) setup
        MUrl = MUrl[:MUrl.find("playlist_basic.m3u8")] + Res
        tmpName = Res[Res.rindex('/') + 1:]
        tmpFile = tmpPath + '/' + tmpName
        response = ss.get(MUrl, headers=headers)
        with open(tmpFile,'wb') as file:
            file.write(response.content)
        chunklist = re.findall(r'.+\.ts',response.text)
        key = re.search(r'URI="([^"]+)"', response.text).group(1)
        MUrl = MUrl[:MUrl.rfind('/')+1]

        #Save key
        response = ss.get(MUrl+key, headers=headers, stream=True)
        with open(tmpFile.replace('chunklist','key')+'key','wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)

        #Save chunks
        print("Donloading..")
        for i in trange(len(chunklist)):
            chunk = chunklist[i]
            response = ss.get(MUrl+chunk, headers=headers, stream=True)
            with open(tmpPath+"/"+chunk, 'wb') as file:
                for schunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(schunk)
        cookiesave = requests.utils.dict_from_cookiejar(ss.cookies)
        pickle.dump(cookiesave, open('./cookie.sav',"wb"))

        #ffmpeg convert
        print("mp4 converting..")
        ffmpeg_path = os.getcwd()+"/ffmpeg.exe"
        input_file = (tmpPath + "/" + tmpName).replace('\\','/')
        output_file = downloadPath +'/'+ title + ".mp4"
        command = [
            ffmpeg_path,
            "-allowed_extensions",
            "ALL",
            "-y",
            "-i",
            input_file,
            "-c",
            "copy",
            output_file
        ]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=input_file[:input_file.rfind("/")])
        process.wait()
        if process.poll() is not None:
            process.terminate()

        #remove tmp files
        shutil.rmtree(tmpPath)

if __name__=='__main__':

    linktype = 0
    while(linktype==0):
        link = input("輸入連結(全部下載)或sn(單集下載):")
        linktype = BahaRequest.baha_link_validate(link)

    # config
    tmpPath = (os.getcwd()+"/Tmp").replace('\\','/')
    downloadPath, Quality = getConfig()
    # downloadPath = "C:/Users/"+os.getlogin()+"/Downloads/Video"
    # Quality = "720"

    if linktype==1:
        BahaRequest.baha_download_request(link, tmpPath, downloadPath, Quality)
    elif linktype==2:
        title = BahaRequest.baha_get_title(link, False)
        downloadPath = downloadPath + '/' + title
        eps = BahaRequest.baha_parse_episodes(link)
        eps = checkbox(eps)
        for ep in eps:
            BahaRequest.baha_download_request(ep, tmpPath, downloadPath, Quality)

    
