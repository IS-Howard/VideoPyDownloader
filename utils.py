import requests
import urllib.request
import json
import re
import random
import time
import os
import shutil
import pickle
import ffmpeg
import concurrent.futures
import threading
from datetime import datetime
from bs4 import BeautifulSoup as bs
from tqdm import tqdm,trange
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def Get_m3u8_url(link, retry=3, retry_wait=30):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument('--headless')
    if os.name == "nt":
        driver_service = ChromeService(executable_path=r"./Tmp/chromedriver.exe")
    else:
        driver_service = ChromeService(executable_path=r"./Tmp/chromedriver")
    driver = webdriver.Chrome(service=driver_service, options=chrome_options)
    driver.get(link)
    start_time=time.time()
    retries = 0
    target = None
    while not target: # wait for the request for retry_wait seconds
        if retries > retry:
            break
        if time.time()-start_time>retry_wait:
            driver.refresh()
            start_time=time.time()
            retries+=1
            print(f"No respond, page refresh {retries} time")
            continue
        for req in driver.requests:
            if req.response and req.url.endswith(".m3u8") and (req.response.status_code==200):
                target=req.url
                break
    driver.quit()
    if target.find("url=")!=-1: # meiju8 url
        target = target[target.find("url=")+4:]

    # level 2 parsing if exist
    response = requests.get(target, verify=False)
    match = re.search(r".*\.m3u8", response.text, re.MULTILINE)
    if not match:
        return target
    hls_line = match.group()
    target = target.replace("/index.m3u8","")
    for s in hls_line.split('/'):
        if s not in target:
            target+='/'+s
    return target

def Download_m3u8(link, TMP, session=None):
    tmpPath = TMP+'/gimy'
    tmpfile = tmpPath+'/0.m3u8'
    if session == None:
        response = requests.get(link)
    else:
        response = session.get(link)

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
    chunklist = []
    for line in response.text.split('\n'):
        if line.startswith("http") or line.endswith(".ts") or line.endswith(".jpeg"):
            chunklist.append(line)
            chunk_sav += str(i)+'.ts'
            i+=1
        else:
            if keyURI and keyURI in line:
                line = line.replace(keyURI,'./key.key')
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
        prefix = link.replace("index.m3u8", "")
        response = requests.get(prefix+keyURI, stream=True)
        with open(tmpPath+'/key.key','wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
    return chunklist

def download_chunk(chunk, index, savepath, progress_bar=None, lock=None, showerr=True, timeout=60, retry=5):
    retries = 0
    while retries < retry:
        try:
            response = requests.get(chunk, stream=True, timeout=timeout)
            if response.status_code == 200:
                with open(f"{savepath}/{index}.ts", 'wb') as file:
                    for schunk in response.iter_content(chunk_size=1024):
                        if schunk:
                            file.write(schunk)
            else:
                if showerr:
                    print(f"Failed to download chunk {index}. Status code: {response.status_code}, Retrying...")
                retries += 1
                continue
                
            if progress_bar:
                with lock:
                    progress_bar.update(1)
                    
            # If download is successful, break the retry loop
            break
        
        except requests.Timeout:
            if showerr:
                print(f"Timeout error downloading chunk {index}. Retrying...")
            retries += 1
            time.sleep(1)
        
        except Exception as e:
            print(f"Error downloading chunk {index}: {str(e)}")
            retries += 1
            continue
    if retries == 5:
        print(f"Failed to download chunk {index}. Retried 5 times, giving up.")

def Download_Chunks(chunklist, TMP, max_threads=15):
    tmpPath = TMP+'/gimy'
    tmpfile = tmpPath+'/0.m3u8'
    with concurrent.futures.ThreadPoolExecutor(max_threads) as executor:
        total_chunks = len(chunklist)
        progress_bar = tqdm(total=total_chunks, desc="Download Progress", unit="chunk")

        lock = threading.Lock() # Mutex lock for updating the progress bar

        for index, chunk_url in enumerate(chunklist):
            executor.submit(lambda url=chunk_url, index=index: download_chunk(url, index, tmpPath, progress_bar, lock))

        # Wait for all tasks to complete
        executor.shutdown()
        progress_bar.close()

def MP4convert(m3u8_file, mp4_file):
    print("mp4 generating..")
    input_file = m3u8_file.replace('\\', '/')
    output_file = mp4_file.replace('\\', '/')
    tmp_file = output_file.rsplit('/', 1)[0] + '/tmp.mp4'

    try:
        # Use ffmpeg to convert m3u8 to mp4
        ffmpeg.input(input_file, allowed_extensions='ALL').output(tmp_file, c='copy').run(overwrite_output=True, quiet=True)
        
        # Rename the temporary file to the final output file
        os.rename(tmp_file, output_file)
        print("Finish!\n")
        return False # no error
    except ffmpeg.Error as e:
        print("Error running FFmpeg:", e.stderr.decode())
        return True # error
    except Exception as e:
        print("Unexpected error:", str(e))
        return True # error
    
def Download_sigle_ts(link, TMP, filename):
    tmpPath = TMP+'/preview'
    try: 
        response = requests.get(link, timeout = 10)
        target = None
        for line in response.text.split('\n'):
            if line.startswith("http") or line.endswith(".ts") or line.endswith(".jpeg"):
                target = line
                break

        if not target:
            print("Err download sigle ts: target not found")
            return
        # prefix?
        if not "http" in target:
            sep = link.split('/')
            prefix = 'https:/'
            for i in range(2,len(sep)-1):
                prefix =prefix+'/'+sep[i] if sep[i] not in target else prefix
            target = prefix +'/'+ target
    except Exception as e:
        print(f"Err: {str(e)}")
        return

    download_chunk(target, filename, tmpPath, timeout=10, retry=1)

def Get_Video_Resolution(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        video_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'video']
        if not video_streams:
            raise ValueError('No video stream found')
        
        width = video_streams[0]['width']
        height = video_streams[0]['height']
        return [width, height]
    except ffmpeg.Error as e:
        print(f"Error resolve video resolution.")
        return [0,0]

def FileNameClean(filename):
    if not filename:
        return None
    windows_invalid_chars = r'[<>:"/\\|?*]'
    cleaned_filename = re.sub(windows_invalid_chars, '', filename)
    cleaned_filename = cleaned_filename.replace('\0', '')
    if len(cleaned_filename) > 255:
        cleaned_filename = cleaned_filename[:255]
    return cleaned_filename
