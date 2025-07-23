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

# Debug flag - set to True to show debug messages
DEBUG = False

def Get_m3u8_chunklist(link, retry=3, retry_wait=30, TMP='./Tmp'):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument('--headless')
    if os.name == "nt":
        driver_service = ChromeService(executable_path=r"./Tmp/chromedriver.exe")
    else:
        driver_service = ChromeService(executable_path=r"./Tmp/chromedriver")
    driver = webdriver.Chrome(service=driver_service, options=chrome_options)
    driver.get(link)
    
    # Wait for page to load and try to trigger video player
    time.sleep(3)
    try:
        # Try to click play button or video element
        play_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='play'], .play-btn, #play, .vjs-play-control, video")
        if play_buttons:
            if DEBUG: print(f"Debug: Found {len(play_buttons)} potential play elements, clicking first one")
            play_buttons[0].click()
            time.sleep(2)
    except Exception as e:
        if DEBUG: print(f"Debug: Could not click play button: {e}")
    
    start_time=time.time()
    retries = 0
    target = None
    reqNum = 0
    if DEBUG: print(f"Debug: Waiting for m3u8 requests...")
    while not target: # wait for the request for retry_wait seconds
        if retries > retry:
            break
        if time.time()-start_time>retry_wait:
            driver.refresh()
            start_time=time.time()
            retries+=1
            print(f"No respond, page refresh {retries} time")
            continue
        
        # Debug: show all requests
        if DEBUG: print(f"Debug: Found {len(driver.requests)} total requests")
        for i in range(reqNum, len(driver.requests)):
            req = driver.requests[i]
            if DEBUG: print(f"Debug: Request {i}: {req.url}")
            if req.response and (req.url.endswith(".m3u8") or req.url.find(".m3u8")!=-1):
                target=req
                reqNum = i+1
                if DEBUG: print(f"Debug: Found m3u8 request: {req.url}")
                
                # Check if this is a PHP script with URL parameter
                if "artplayer" in req.url and "url=" in req.url:
                    import urllib.parse
                    parsed_url = urllib.parse.urlparse(req.url)
                    params = urllib.parse.parse_qs(parsed_url.query)
                    if 'url' in params:
                        actual_m3u8_url = params['url'][0]
                        if DEBUG: print(f"Debug: Extracting actual m3u8 URL: {actual_m3u8_url}")
                        
                        # Fetch the actual m3u8 content directly
                        try:
                            response = requests.get(actual_m3u8_url, timeout=30)
                            if response.status_code == 200:
                                if DEBUG: print(f"Debug: Successfully fetched actual m3u8, length: {len(response.text)}")
                                # Create a mock target with the real content
                                class MockTarget:
                                    def __init__(self, url, content):
                                        self.url = url
                                        self.response = MockResponse(content.encode('utf-8'))
                                
                                class MockResponse:
                                    def __init__(self, body):
                                        self.body = body
                                
                                target = MockTarget(actual_m3u8_url, response.text)
                                break
                        except Exception as e:
                            if DEBUG: print(f"Debug: Failed to fetch actual m3u8: {e}")
                
                break
    time.sleep(2)

    if not target:
        if DEBUG: print("Debug: No m3u8 requests found in browser traffic")
        return []

    # level 2 parsing
    body = target.response.body
    try:
        res = body.decode("utf-8")
    except UnicodeDecodeError:
        try:
            res = body.decode("latin-1")
        except UnicodeDecodeError:
            res = body.decode("utf-8", errors="replace")
    match = re.search(r".*\.m3u8", res, re.MULTILINE)
    if match:
        while driver.execute_script("return document.readyState") != "complete":
            time.sleep(1)
        for i in range(reqNum, len(driver.requests)):
            req = driver.requests[i]
            if req.response and req.url.endswith(".m3u8"):
                target=req
                body = target.response.body
                try:
                    res = body.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        res = body.decode("latin-1")
                    except UnicodeDecodeError:
                        res = body.decode("utf-8", errors="replace")
                match = re.search(r".*\.m3u8", res, re.MULTILINE)
                if match:
                    continue
                break
    driver.quit()
    
    if DEBUG: print(f"Debug: About to parse m3u8 content, length: {len(res)}")
    if DEBUG: print(f"Debug: First 200 chars of m3u8 content: {res[:200]}")
    return Parse_m3u8(TMP, res, target.url)

def Parse_m3u8(TMP, resStr, link):
    tmpPath = TMP+'/gimy'
    tmpfile = tmpPath+'/0.m3u8'

    # check m3u8 key
    match = re.search(r'URI="([^"]+)"', resStr)
    if match:
        keyURI = match.group(1)
    else:
        keyURI = None

    # save m3u8 list
    with open(tmpPath+'/original.m3u8','w', encoding='utf-8') as file:
        file.write(resStr)
    chunk_sav = '' 
    i=0
    chunklist = []
    for line in resStr.split('\n'):
        if line.startswith("http") or line.endswith(".ts") or line.endswith(".jpeg"):
            chunklist.append(line)
            if DEBUG: print(f"Debug: Found chunk: {line}")
            chunk_sav += str(i)+'.ts'
            i+=1
        else:
            if keyURI and keyURI in line:
                line = line.replace(keyURI,'./key.key')
            chunk_sav += line
        chunk_sav += '\n'
    with open(tmpfile,"w", encoding='utf-8') as file:
        file.write(chunk_sav)

    # chunk link prefix?
    if chunklist and not "http" in chunklist[0]:
        sep = link.split('/')
        prefix = 'https:/'
        for i in range(2,len(sep)-1):
            prefix =prefix+'/'+sep[i] if sep[i] not in chunklist[0] else prefix
        chunklist = [prefix+'/'+x for x in chunklist]
    
    if DEBUG: print(f"Debug: Final chunklist has {len(chunklist)} items")
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
    
def Download_single_ts(link, TMP, filename):
    tmpPath = TMP+'/preview'
    try: 
        response = requests.get(link, timeout = 10)
        target = None
        for line in response.text.split('\n'):
            if line.startswith("http") or line.endswith(".ts") or line.endswith(".jpeg"):
                target = line
                break

        if not target:
            print("Err download single ts: target not found")
            return
        # prefix?
        if not "http" in target:
            sep = link.split('/')
            prefix = 'https:/'
            for i in range(2,len(sep)-1):
                prefix =prefix+'/'+sep[i] if sep[i] not in target else prefix
            target = prefix +'/'+ target
        download_chunk(target, filename, tmpPath, timeout=10, retry=1)
    except Exception as e:
        print(f"Err: {str(e)}")
        return


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
