from utils import *

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

    def Get_Title_Link(site, sel_src=1):
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
                links = Get_m3u8_url(site)

            return title, links

        except:
            print("Err: Get_Title_Link")
            return None, None

    def Download_Request(site, TMP, downloadPath, max_threads=15, sel_src=1):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, link = AnimeOne.Get_Title_Link(site, sel_src)
        if not link or not title:
            print("Connection Failed. Source may be invalid!\n")
            return False
        print(title)

        Download_Chunks(Download_m3u8(link, TMP), TMP)

        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False

        #remove tmp files
        shutil.rmtree(tmpPath)
        return True