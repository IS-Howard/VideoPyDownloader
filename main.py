import requests
import browser_cookie3
import json
import random
from datetime import datetime
import re
import time
import os
import subprocess
from tqdm import tqdm,trange
import shutil
from PyInquirer import prompt
import pickle
from bs4 import BeautifulSoup as bs
import urllib.request

def Get_Config():
    with open('config.txt', 'r') as file:
        contents = file.read()
        download_path_match = re.search(r'Download Path:\s*(.*)', contents) # downloadPath = "C:/Users/"+os.getlogin()+"/Downloads/Video"
        quality_match = re.search(r'Quality:\s*(\d+)', contents)
        chromeP_match = re.search(r'Chrome Profile:\s*(.+)', contents)

        # Extract the download path and quality if found
        downloadPath = download_path_match.group(1) if download_path_match else None
        Quality = quality_match.group(1) if quality_match else None
        chromeP = chromeP_match.group(1) if chromeP_match else None

    return downloadPath, Quality, chromeP

def Get_Link_Type(link,chromeP='Default'):
    if link.find("anime1.me")!=-1: #anime1 0(bad) 3(sn) 4(full)
        return Anime1.Link_Validate(link,chromeP)
    return Baha.Link_Validate(link) #baha 0(bad) 1(sn) 2(full)


def CheckBox(eps):
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

def MP4convert(m3u8_file, mp4_file, ffmpeg_path=None):
    print("mp4 generating..")
    if not ffmpeg_path:
        ffmpeg_path = os.getcwd()+"/ffmpeg.exe"
    input_file = m3u8_file.replace('\\','/')
    output_file = mp4_file.replace('\\','/')

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

class Baha:

    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Referer': 'https://ani.gamer.com.tw/',
        'origin': 'https://ani.gamer.com.tw'
    }

    cookie_file = './Tmp/Cookie1'

    def RandomString(K):
        S = "abcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(random.choice(S) for i in range(K))

    def Get_Title(sn, ep=True):
        if sn.startswith("http"):
            sn = sn.split("=")[-1]
        headers = Baha.headers
        response = requests.get("https://api.gamer.com.tw/mobile_app/anime/v2/video.php?sn="+sn, headers=headers)
        rx = re.compile(r'"title":"(.*?)"},"anime"')
        utitle = rx.findall(response.text)[0]
        title = json.loads('"%s"' %utitle)
        if not ep:
            return title.rsplit(" ",1)[0]
        return title
    
    def Parse_Episodes(link):
        headers = Baha.headers
        response = requests.get(link, headers=headers)
        return re.findall(r'"\?sn=(\d{5})">(\d+\.?\d?)<', response.text)

    def Link_Validate(link):
        linktype = 0 # bad link
        if not link.startswith("http"):
            link = "https://ani.gamer.com.tw/animeVideo.php?sn="+link
            linktype = 1 # sn
        else: # full link
            if link.find("https://ani.gamer.com.tw/animeVideo.php?sn=")==-1:
                return 0
            linktype = 2

        headers = Baha.headers
        response = requests.get(link, headers=headers)
        if response.text.find("目前無此動畫或動畫授權已到期！")!=-1:
            print("err: 目前無此動畫或動畫授權已到期")
            return 0
        return linktype

    def Set_Session(chromeP="Default"):
        ss = requests.Session()

        if os.path.isfile(Baha.cookie_file):
            cookie_set = 2
        else:
            cookie_set = 1
        
        if cookie_set == 1:   # load from chrome
            try:
                cookies = browser_cookie3.chrome(domain_name='gamer.com', cookie_file=os.getenv("APPDATA") + "/../Local/Google/Chrome/User Data/"+chromeP+"/Network/Cookies")
                ss.cookies = cookies
                pickle.dump(requests.utils.dict_from_cookiejar(cookies), open(Baha.cookie_file,"wb"))
            except:
                print("Error when loading cookies, please make sure tuning off chrome first!")
                return None
        elif cookie_set == 2: # load request cookie file
            ss.cookies = requests.utils.cookiejar_from_dict(pickle.load(open(Baha.cookie_file,'rb')))
        return ss
            
    def Download_Request(sn, tmpPath, downloadPath, Quality="720", chromeP="Default"):
        # path initialize
        tmpPath = tmpPath+'/tmp'+sn
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        # request config and cookie
        headers = Baha.headers
        ss = Baha.Set_Session(chromeP=chromeP)
        if not ss:
            return

        #Get Title
        title = Baha.Get_Title(sn)
        print(title)

        #ID
        response = ss.get('https://ani.gamer.com.tw/ajax/getdeviceid.php?id=', headers=headers)
        load = json.loads(response.text)
        deviceID = load["deviceid"]

        #Access
        response = ss.get('https://ani.gamer.com.tw/ajax/token.php?adID=undefined&sn='+sn+ "&device="+deviceID+"&hash="+Baha.RandomString(12), headers=headers)
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

        #Get video m3u8 link start
        response = ss.get('https://ani.gamer.com.tw/ajax/videoStart.php?sn='+sn, headers=headers)
        response = ss.get('https://ani.gamer.com.tw/ajax/m3u8.php?sn='+sn+'&device='+deviceID, headers=headers)
        load = json.loads(response.text)
        MUrl = load["src"]

        #Get link of M3U8 list
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
            print("Get List Link Fail")
            #remove tmp files
            shutil.rmtree(tmpPath)
            return
        
        #M3U8 setup
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

        #Save .ts files
        print("Donloading..")
        for i in trange(len(chunklist)):
            chunk = chunklist[i]
            response = ss.get(MUrl+chunk, headers=headers, stream=True)
            with open(tmpPath+"/"+chunk, 'wb') as file:
                for schunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(schunk)
        cookiesave = requests.utils.dict_from_cookiejar(ss.cookies)
        pickle.dump(cookiesave, open(Baha.cookie_file,"wb"))

        #ffmpeg convert
        MP4convert(tmpPath + "/" + tmpName, downloadPath +'/'+ title + ".mp4")

        #remove tmp files
        shutil.rmtree(tmpPath)

class Anime1():

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'}
    headers2 = {'Content-Type': 'application/x-www-form-urlencoded','User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'}
    cookies = None

    def Set_Cookie(chromeP='Default'):
        try:
            cookies = browser_cookie3.chrome(domain_name='.anime.me', cookie_file=os.getenv("APPDATA") + "/../Local/Google/Chrome/User Data/"+chromeP+"/Network/Cookies")
            Anime1.cookies = cookies
            return True
        except:
            print("Error when loading cookies, please make sure tuning off chrome first!")
            return False

    def Link_Validate(link,chromeP='Default'):
        if not Anime1.Set_Cookie(chromeP):
            print("err: Cookie")
            return 0
        
        title, link = Anime1.Get_Title_Link(link)

        if title==None:
            print('err: None')
            return 0
        
        if title=='找不到符合條件的頁面':
            print("err: ", title)
            return 0
        
        if title=='Just a moment...':
            print("Please reflesh chrome on https://anime1.me/")
            return 0
        
        if isinstance(link, str):
            return 3
        
        if isinstance(link, list):
            return 4
        
        return 0

    def Get_Title_Link(site):
        response = requests.get(site, headers=Anime1.headers, cookies=Anime1.cookies)
        soup = bs(response.text, 'html.parser')

        title_tag = soup.find('title')
        title_text = title_tag.text if title_tag else None
        title = title_text.split(" – Anime1.me")[0]

        if site.find("category")!=-1:
        # return title with all eps' links
            posts = soup.find_all('h2')
            if not posts:
                return None, None
            links = []
            for post in reversed(posts):
                link = post.find('a')['href']
                ep = post.text.split(' [')[-1].replace("]","")
                links.append((link,ep))
        else:
        # return sigle eq tile and api link
            target = soup.find('video')
            if not target:
                return None, None
            target = target.get('data-apireq')
            links = 'd='+target

        return title, links
    
    def cookie_header(cookies):
        res = ''
        for name in cookies:
            if len(res) > 0:
                res +='; '
            res += name + "=" + cookies[name]#.decode()
        return res

    def Download_Request(site, downloadPath, chromeP="Default"):
        #path
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        # get local cookies
        if not Anime1.Set_Cookie(chromeP):
            return

        # get info for api
        title, target = Anime1.Get_Title_Link(site)
        print(title)

        # Call API
        ss = requests.Session()
        response = ss.post('https://v.anime1.me/api', data=target.encode('utf-8'), headers=Anime1.headers2, cookies=Anime1.cookies)
        match = re.search(r'//[^"]+.mp4', response.text)
        link = "https:"+match.group() if match else None
        if not link:
            print("err: access api fail")

        # cookie header update
        cookies = requests.utils.dict_from_cookiejar(ss.cookies)
        headers3 = {'Cookie': Anime1.cookie_header(cookies)}

        # Download
        request = urllib.request.Request(link, headers=headers3)
        response = urllib.request.urlopen(request)
        filename = downloadPath+title+".mp4"
        # Get the total file size from the Content-Length header, if available
        total_size = int(response.headers.get('Content-Length', 0))
        bytes_so_far = 0

        filename = downloadPath+title+".mp4"
        print("Donloading..")
        with open(filename, 'wb') as file, tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
            chunk_size = 1024  # You can adjust the chunk size as needed (e.g., 1024 for 1 KB)

            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break

                file.write(chunk)
                bytes_so_far += len(chunk)
                pbar.update(len(chunk))


        




if __name__=='__main__':

    # config
    tmpPath = (os.getcwd()+"/Tmp").replace('\\','/')
    downloadPath, Quality, chromeP = Get_Config()

    go = True
    # check chrome profile
    if not os.path.isfile(os.getenv("APPDATA") + "/../Local/Google/Chrome/User Data/"+chromeP+"/Network/Cookies"):
        print("Cookie not exist, please check profile setting")
        go = False


    while(go):
        link = input("輸入連結(全部下載)或sn(單集下載):")
        if link=='exit':
            break
        linktype = Get_Link_Type(link,chromeP)
        if linktype==0:
            continue

        if linktype==1:
            Baha.Download_Request(link, tmpPath, downloadPath, Quality, chromeP)
        elif linktype==2:
            title = Baha.Get_Title(link, False)
            downloadPath = downloadPath + '/' + title
            eps = Baha.Parse_Episodes(link)
            eps = CheckBox(eps)
            for ep in eps:
                Baha.Download_Request(ep, tmpPath, downloadPath, Quality, chromeP)
        elif linktype==3:
            Anime1.Download_Request(link, downloadPath, chromeP)
        elif linktype==4:
            title,eps = Anime1.Get_Title_Link(link)
            downloadPath = downloadPath + '/' + title + '/'
            eps = CheckBox(eps)
            for ep in eps:
                Anime1.Download_Request(ep, downloadPath, chromeP)

    
