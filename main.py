import requests
import browser_cookie3
import urllib.request
from bs4 import BeautifulSoup as bs

import json
import re

import random
from datetime import datetime
import time
import os
import shutil
import pickle

from tqdm import tqdm,trange

import subprocess
import concurrent.futures
import threading

from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By

def Get_Config():
    with open('config', 'r') as file:
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
    elif link.find("gimy.su")!=-1 or link.find("gimy.ai")!=-1: #gimy 0(bad) 5(sn) 6(full)
        return Gimy.Link_Validate(link)
    elif link.find("anime1.one")!=-1:
        return AnimeOne.Link_Validate(link)
    return Baha.Link_Validate(link) #baha 0(bad) 1(sn) 2(full)

def Multiple_Download_Select(eps):
    try:
        print(f"總共有{len(eps)}集")
        getall = input("全部下載(y/n): ")
        if getall=='n' or getall=='N':
            st = int(input(f"從第幾集開始?(1~{len(eps)}): "))
            ed = int(input(f"下載到第幾集?({st}~{len(eps)}): "))
            st-=1
        else:
            st=0
            ed=len(eps)
        if not st > ed:
            return st, ed
        else:
            print("Bad")
            return None,None

    except Exception as e:
        print("Error:", str(e))
        return None,None

def MP4convert(m3u8_file, mp4_file, ffmpeg_path=None):
    print("mp4 generating..")
    if not ffmpeg_path:
        ffmpeg_path = os.getcwd()+"/Tmp/ffmpeg.exe"
    input_file = m3u8_file.replace('\\','/')
    output_file = mp4_file.replace('\\','/')
    tmp_file = output_file.rsplit('/',1)[0]+'/tmp.mp4'

    command = [
        ffmpeg_path,
        "-allowed_extensions",
        "ALL",
        "-y",
        "-i",
        input_file,
        "-c",
        "copy",
        tmp_file
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd())
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print("FFmpeg process returned an error code:", process.returncode)
            print("FFmpeg Output:", stdout.decode())
            print("FFmpeg Error:", stderr.decode())
        os.rename(tmp_file, output_file)
        print("Finish!\n")
        return False # no error
    except Exception as e:
        print("Error running FFmpeg:", str(e))
        return True # error

class Baha:

    headers = {
        "Origin": "https://ani.gamer.com.tw",
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
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
        soup = bs(response.text, 'html.parser')
        region = soup.find(class_="season")
        version_name = [x.get_text() for x in region.find_all("p")]
        version_region = region.find_all("ul")
        print('\n'.join([f"{i}.{y}" for i, y in enumerate(version_name, 1)]))
        try:
            if len(version_name) > 1:
                sel = input(f"選擇版本({1}~{len((version_name))}): ")
                sel = int(sel)-1
            else:
                sel = 0
            sel_region = str(version_region[sel])
            return re.findall(r'"\?sn=(\d+)">\d+\.?\d?<', sel_region)
        except Exception as e:
            print(f"ERR: {str(e)}")
            return None

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
            
    def Download_Request(sn, TMP, downloadPath, Quality="720", chromeP="Default"):
        # path initialize
        tmpPath = TMP+'/tmp'+sn
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        # request config and cookie
        headers = Baha.headers
        ss = Baha.Set_Session(chromeP=chromeP)
        if not ss:
            shutil.rmtree(tmpPath)
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
            print("Access Fail (Login in Chrome again may fix)")
            #remove tmp files
            shutil.rmtree(tmpPath)
            os.remove(Baha.cookie_file)
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
                    Res = nextLine.strip()
                    break
        if Res == '':
            print("Get List Link Fail (Login in Chrome again may fix)")
            #remove tmp files
            shutil.rmtree(tmpPath)
            os.remove(Baha.cookie_file)
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
        if MP4convert(tmpPath + "/" + tmpName, downloadPath +'/'+ title + ".mp4"):
            return

        #remove tmp files
        shutil.rmtree(tmpPath)

class Anime1:

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
        try:
            response = requests.get(site, headers=Anime1.headers, cookies=Anime1.cookies)
            soup = bs(response.text, 'html.parser')
            title_text =soup.find('title').text
            title = title_text.split(" – Anime1.me")[0]

            if site.find("category")!=-1:
            # return title with all eps' links
                links = []
                pages = 1
                site = site.split('/page/')[0]
                while True:
                    r2 = requests.get(site+'/page/'+str(pages+1), headers=Anime1.headers, cookies=Anime1.cookies)
                    s2 = bs(r2.text, 'html.parser')
                    if '找不到符合條件的頁面' in s2.find('title').text:
                        break
                    pages += 1
                for i in range(pages,1,-1):
                    r2 = requests.get(site+'/page/'+str(i), headers=Anime1.headers, cookies=Anime1.cookies)
                    s2 = bs(r2.text, 'html.parser')
                    posts = s2.find_all('h2')
                    for post in reversed(posts):
                        if post.find('a'):
                            link = post.find('a')['href']
                            links.append(link)
                r2 = requests.get(site, headers=Anime1.headers, cookies=Anime1.cookies)
                s2 = bs(r2.text, 'html.parser')
                posts = s2.find_all('h2')
                for post in reversed(posts):
                    if post.find('a'):
                        link = post.find('a')['href']
                        links.append(link)
            else:
            # return sigle eq tile and api link
                target = soup.find('video')
                target = target.get('data-apireq')
                links = 'd='+target

            return title, links

        except:
            print("Err: Get_Title_Link")
            return None, None
    
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

class AnimeOne:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'}

    def Link_Validate(link):
        title, link = AnimeOne.Get_Title_Link(link)

        if title==None:
            print('err: None')
            return 0
        
        if title=='找不到符合條件的頁面':
            print("err: ", title)
            return 0
        
        if isinstance(link, str):
            print(link)
            return 7
        
        if isinstance(link, list):
            return 8
        
        return 0

    def Get_Title_Link(site):
        try:
            response = requests.get(site, headers=AnimeOne.headers)
            soup = bs(response.text, 'html.parser')
            title_text =soup.find('title').text
            title = title_text.split(" – Anime1.one")[0]

            if site.find("-")==-1:
                # return title with all eps' links
                links = []
                pages = 1
                site = site.split('/page/')[0]
                while True:
                    r2 = requests.get(site+'page/'+str(pages+1), headers=AnimeOne.headers)
                    s2 = bs(r2.text, 'html.parser')
                    posts = s2.find_all('h2')
                    if len(posts) == 1:
                        break
                    pages += 1
                for i in range(pages,1,-1):
                    r2 = requests.get(site+'page/'+str(i), headers=AnimeOne.headers)
                    s2 = bs(r2.text, 'html.parser')
                    posts = s2.find_all('h2')
                    for post in reversed(posts):
                        if post.find('a'):
                            link = post.find('a')['href']
                            links.append("https://anime1.one"+link)
                r2 = requests.get(site, headers=AnimeOne.headers)
                s2 = bs(r2.text, 'html.parser')
                posts = s2.find_all('h2')
                for post in reversed(posts):
                    if post.find('a'):
                        link = post.find('a')['href']
                        links.append("https://anime1.one"+link)
            else:
            # return sigle eq tile and api link
                chrome_options = webdriver.ChromeOptions()
                chrome_options.add_argument("--log-level=3")
                chrome_options.add_argument('--headless')
                driver_service = ChromeService(executable_path=r"./Tmp/chromedriver.exe")
                driver = webdriver.Chrome(service=driver_service, options=chrome_options)
                driver.get(site)
                iframe_xpath = '//div[2]/p[1]/iframe[1]'
                iframe = driver.find_element(By.XPATH, iframe_xpath)
                driver.switch_to.frame(iframe)
                src = driver.find_element(By.TAG_NAME, 'source')
                links = src.get_attribute('src') #m3u8 link

            return title, links

        except:
            print("Err: Get_Title_Link")
            return None, None
    

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, link = AnimeOne.Get_Title_Link(site)
        if not link or not title:
            print("Connection Failed. Source may be invalid!\n")
            return False
        print(title)


        response = requests.get(link)
        for line in response.text.split("\n"):
            if line.endswith('m3u8'):
                overlap = line.split("/")[1]
                link = (link.split(overlap)[0]+overlap+line.split(overlap)[1])

        # m3u8 link
        response = requests.get(link)
        chunklist = re.findall(r'.+\.ts',response.text)

        # check m3u8 key
        match = re.search(r'URI="([^"]+)"', response.text)
        if match:
            keyURI = match.group(1)
        else:
            keyURI = None

        # save m3u8 list
        with open(tmpPath+'/original.m3u8','wb') as file:
            file.write(response.text.encode("utf-8"))
        chunk_sav = '' 
        i=0
        for line in response.text.split('\n'):
            if line.endswith(".ts"):
                chunk_sav += str(i)+'.ts'
                i+=1
            else:
                if keyURI and keyURI in line:
                    line = line.replace(keyURI,'/key.key')
                chunk_sav += line
            chunk_sav += '\n'
        with open(tmpfile,"w") as file:
            file.write(chunk_sav)

        # chunk link prefix?
        if not "http" in chunklist[0]:
            sep = link.split('/')
            prefix = 'https:/'
            for i in range(2,len(sep)-1):
                prefix =prefix+'/'+sep[i] if sep[i] not in chunklist[0] else prefix
            chunklist = [prefix+'/'+x for x in chunklist]
        # Download key?
        if keyURI:
            response = requests.get(prefix+keyURI, stream=True)
            with open(tmpPath+'/key.key','wb') as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)

        # Download from m3u8 link
        with concurrent.futures.ThreadPoolExecutor(max_threads) as executor:
            total_chunks = len(chunklist)
            progress_bar = tqdm(total=total_chunks, desc="Download Progress", unit="chunk")

            lock = threading.Lock() # Mutex lock for updating the progress bar

            for index, chunk_url in enumerate(chunklist):
                executor.submit(lambda url=chunk_url, index=index: Gimy.download_chunk(url, index, tmpPath, progress_bar, lock))

            # Wait for all tasks to complete
            executor.shutdown()
            progress_bar.close()

        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False

        #remove tmp files
        shutil.rmtree(tmpPath)
        return True

class Gimy:
    def Link_Validate(site):
        title, link = Gimy.Get_Title_Link(site,False)

        if title==None or link==None:
            print('err: None')
            return 0
        
        if title=='404 not found' or title=='System Error':
            print("err: Bad Page!")
            return 0
        
        if link==1:
            return 5
        
        if link==2:
            return 6
        
        return 0

    def Get_Title_Link(site, get_link=True):
        response = requests.get(site)
        soup = bs(response.text, 'html.parser')

        title_tag = soup.find('title')
        title = title_tag.text if title_tag else None
        if not title:
            print("title not found")
            return None, None

        prefix = "https://gimy.ai" if "gimy.ai" in site else "https://gimy.su"
        if "vod" in site:
        # return title with all eps' links
            title = title.split('線上看')[0] #main
            if get_link:
                yun_all = soup.find_all(class_='gico')
                yun_name = [x.text for x in yun_all]
                print('\n'.join([f"{i}.{y}" for i, y in enumerate(yun_name, 1)]))
                try:
                    sel = input(f"選擇來源(1~{len(yun_all)}): ")
                    sel = int(sel)-1
                    yun = yun_all[sel]
                    ele_list =  yun.find_parent().find_next_sibling().find_all('a')
                    links = [prefix+x['href'] for x in ele_list]
                    lst = [x.get_text() for x in ele_list]
                    if sum(lst[i] >= lst[i + 1] for i in range(len(lst) - 1)) > len(lst)//2: #loose decending ordered
                        links.reverse()
                except  Exception as e:
                    print(str(e))
                    return None, None
            else:
                links = 2
        else:
        # return sigle eq tile and api link
            title = title.replace(" - Gimy 劇迷", "") #ep
            title = title.replace("線上看","")
            links = Gimy.Get_MUrl(site) if get_link else 1

        return title, links
    
    def Get_MUrl(link):

        try:
            target = None
            if "gimy.su" in link:
                response = requests.get(link)
                match = re.search(r'"url":"([^"]+.m3u8)"',response.text)
                target = match.group(1) if match else None
            elif "gimy.ai" in link:
                # use selenium to render javascript and get m3u8 link
                chrome_options = webdriver.ChromeOptions()
                chrome_options.add_argument("--log-level=3")
                chrome_options.add_argument('--headless')
                driver_service = ChromeService(executable_path=r"./Tmp/chromedriver.exe")
                driver = webdriver.Chrome(service=driver_service, options=chrome_options)
                driver.get(link)
                start_time=time.time()
                retry = 0
                while not target: # wait for the request for 60s
                    if retry > 3:
                        break
                    if time.time()-start_time>30:
                        driver.refresh()
                        start_time=time.time()
                        retry+=1
                        print(f"No respond, page refresh {retry} time")
                        continue
                    for req in driver.requests:
                        if req.response and req.url.endswith(".m3u8") and (req.response.status_code==200):
                            target=req.url
                            break
                driver.quit()
                print('\n')

            target = target.replace("\\", '')

            response = requests.get(target)
            match = re.search(r".*\.m3u8", response.text, re.MULTILINE)
            if not match:
                return target
            hls_line = match.group()
            target = target.replace("/index.m3u8","")
            for s in hls_line.split('/'):
                if s not in target:
                    target+='/'+s
            return target
        except Exception as e:
            print(str(e))
            return None
        
    def download_chunk(chunk, index, savepath, progress_bar=None, lock=None, showerr=True):
        try:
            response = requests.get(chunk, stream=True, timeout=60)
            if response.status_code == 200:
                with open(f"{savepath}/{index}.ts", 'wb') as file:
                    for schunk in response.iter_content(chunk_size=1024):
                        if schunk:
                            file.write(schunk)
            else:
                if showerr:
                    print(f"Failed to download chunk {index}. Status code: {response.status_code}")
                
            if progress_bar:
                with lock:
                    progress_bar.update(1)
        except Exception as e:
            print(f"Error downloading chunk {index}: {str(e)}")

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, link = Gimy.Get_Title_Link(site)
        if not link or not title:
            print("Connection Failed. Source may be invalid!\n")
            return False
        print(title)

        # m3u8 link
        response = requests.get(link)
        chunklist = re.findall(r'.+\.ts',response.text)

        # check m3u8 key
        match = re.search(r'URI="([^"]+)"', response.text)
        if match:
            keyURI = match.group(1)
        else:
            keyURI = None

        # save m3u8 list
        with open(tmpPath+'/original.m3u8','wb') as file:
            file.write(response.text.encode("utf-8"))
        chunk_sav = '' 
        i=0
        for line in response.text.split('\n'):
            if line.endswith(".ts"):
                chunk_sav += str(i)+'.ts'
                i+=1
            else:
                if keyURI and keyURI in line:
                    line = line.replace(keyURI,'/key.key')
                chunk_sav += line
            chunk_sav += '\n'
        with open(tmpfile,"w") as file:
            file.write(chunk_sav)

        # chunk link prefix?
        if not "http" in chunklist[0]:
            sep = link.split('/')
            prefix = 'https:/'
            for i in range(2,len(sep)-1):
                prefix =prefix+'/'+sep[i] if sep[i] not in chunklist[0] else prefix
            chunklist = [prefix+'/'+x for x in chunklist]
        # Download key?
        if keyURI:
            response = requests.get(prefix+keyURI, stream=True)
            with open(tmpPath+'/key.key','wb') as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)

        # Download from m3u8 link
        with concurrent.futures.ThreadPoolExecutor(max_threads) as executor:
            total_chunks = len(chunklist)
            progress_bar = tqdm(total=total_chunks, desc="Download Progress", unit="chunk")

            lock = threading.Lock() # Mutex lock for updating the progress bar

            for index, chunk_url in enumerate(chunklist):
                executor.submit(lambda url=chunk_url, index=index: Gimy.download_chunk(url, index, tmpPath, progress_bar, lock))

            # Wait for all tasks to complete
            executor.shutdown()
            progress_bar.close()

        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False

        #remove tmp files
        shutil.rmtree(tmpPath)
        return True

if __name__=='__main__':

    # config
    TMP = (os.getcwd()+"/Tmp").replace('\\','/')
    downloadPath0, Quality, chromeP = Get_Config()

    go = True
    # check chrome profile
    if not os.path.isfile(os.getenv("APPDATA") + "/../Local/Google/Chrome/User Data/"+chromeP+"/Network/Cookies"):
        print("Cookie not exist, please check profile setting")
        go = False


    while(go):
        print("----------------------------------------")
        print("Baha-完整連結(全部下載)或sn(單集)")
        print("Anime1-頁面網址(全部)或(單集)")
        print("Gimy-頁面網址(全部)或(單集)")
        print("----------------------------------------")
        link = input("輸入:")
        if link=='exit':
            break
        linktype = Get_Link_Type(link,chromeP)
        if linktype==0:
            continue

        if linktype==1:
            Baha.Download_Request(link, TMP, downloadPath0, Quality, chromeP)
        elif linktype==2:
            title = Baha.Get_Title(link, False)
            downloadPath = downloadPath0 + '/' + title
            eps = Baha.Parse_Episodes(link)
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Baha.Download_Request(eps[i], TMP, downloadPath, Quality, chromeP)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==3:
            Anime1.Download_Request(link, downloadPath0, chromeP)
        elif linktype==4:
            title,eps = Anime1.Get_Title_Link(link)
            downloadPath = downloadPath0 + '/' + title + '/'
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Anime1.Download_Request(eps[i], downloadPath, chromeP)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==5:
            Gimy.Download_Request(link, TMP, downloadPath0)
        elif linktype==6:
            title, eps = Gimy.Get_Title_Link(link)
            downloadPath = downloadPath0 + '/' + title + '/'
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Gimy.Download_Request(eps[i], TMP, downloadPath)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==7:
            AnimeOne.Download_Request(link,TMP,downloadPath0)
        elif linktype==8:
            title, eps = AnimeOne.Get_Title_Link(link)
            downloadPath = downloadPath0 + '/' + title + '/'
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    AnimeOne.Download_Request(eps[i], TMP, downloadPath)
            except Exception as e:
                print("Error:", str(e))




    
