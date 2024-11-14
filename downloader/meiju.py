from utils import *

class Meiju:
    def Link_Validate(site):
        if "content" in site:
            return 0
        rep = requests.get(site,verify=False)
        if "meijutt.net/video" in site and rep.status_code == 200:
            return 10
        return 0

    def Get_Title_Link(site):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument('--headless')
        if os.name == "nt":
            driver_service = ChromeService(executable_path=r"./Tmp/chromedriver.exe")
        else:
            driver_service = ChromeService(executable_path=r"./Tmp/chromedriver")
        driver = webdriver.Chrome(service=driver_service, options=chrome_options)
        driver.get(site)

        title = ''
        result = re.search(r'《(.*?)》', driver.title)
        if result:
            title = result.group(1)
        if not title or not result:
            print("title not found")
            return "", []

        tab = driver.find_element(By.CSS_SELECTOR, r'#play-list > div.current')
        ele_list = tab.find_elements(By.CSS_SELECTOR, 'a')
        links = [ep.get_attribute('href') for ep in ele_list]

        return FileNameClean(title), links

    def Download_Request(link, title, TMP, downloadPath, max_threads=15):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        chunks = Get_m3u8_chunklist(link)

        print(title)
        Download_Chunks(chunks, TMP)

        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False

        #remove tmp files
        shutil.rmtree(tmpPath)
        return True