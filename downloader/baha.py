from utils import *

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
            return FileNameClean(title.rsplit(" ",1)[0])
        return FileNameClean(title)
    
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

    def Set_Session():
        ss = requests.Session()

        if os.path.isfile(Baha.cookie_file):
            cookie_set = True
        else:
            cookie_set = False
        
        if not cookie_set: # login process
            try:
                Baha.Login()
            except Exception as e:
                print(f"Error when loggin in!  err: {str(e)}")
                return None
        ss.cookies = requests.utils.cookiejar_from_dict(pickle.load(open(Baha.cookie_file,'rb')))
        return ss

    def Login():
        driver = Driver(headless2=True, extension_dir='./Tmp/extension')

        # login
        link = "https://user.gamer.com.tw/login.php"
        driver.open(link)
        username = input("請輸入帳號: ")
        password = input("請輸入密碼: ")
        driver.type('#form-login > input:nth-child(1)', username)
        driver.type('#form-login > div.password-box > input', password)
        # pass recaptcha
        wait = False
        if driver.is_element_visible('iframe[title="reCAPTCHA"]'):
            driver.switch_to_frame('iframe[title="reCAPTCHA"]')
            time.sleep(1)
            driver.click('#recaptcha-anchor')
            while not driver.is_element_visible('.recaptcha-checkbox-checked'):
                driver.switch_to_default_window()
                if driver.is_element_visible('iframe[title="recaptcha challenge expires in two minutes"]') and not wait:
                    driver.switch_to_frame('iframe[title="recaptcha challenge expires in two minutes"]')
                    driver.wait_for_element('.help-button-holder', timeout=5)
                    driver.click('.help-button-holder')
                    print("Clicked reCAPTCHA solve button")
                    wait = True
                time.sleep(1)
                if driver.is_element_visible('iframe[title="reCAPTCHA"]'):
                    driver.switch_to_frame('iframe[title="reCAPTCHA"]')
        driver.switch_to_default_window()
        driver.click('#btn-login')
        print("Login success!")
        time.sleep(5)

        # save cookies
        selenium_cookies = driver.get_cookies()
        cookies_dict = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        pickle.dump(cookies_dict, open(Baha.cookie_file,"wb"))
        pickle.dump(cookies_dict, open(Baha.cookie_file+".bak","wb"))
            
    def Download_Request(sn, TMP, downloadPath, Quality="720"):
        # path initialize
        tmpPath = TMP+'/tmp'+sn
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        # request config and cookie
        headers = Baha.headers
        ss = Baha.Set_Session()
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
            print("Access Fail")
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
        if DEBUG:
            print("MUrl:", MUrl)

        #Get link of M3U8 list
        response = ss.get(MUrl, headers=headers)
        sr = response.text
        if DEBUG:
            print("res:", sr)
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
            print("Get List Link Fail")
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