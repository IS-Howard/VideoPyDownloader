from utils import *

class Anime1:

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'}
    headers2 = {'Content-Type': 'application/x-www-form-urlencoded','User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'}
    cookies = None

    def Link_Validate(link):
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
            # return single eq tile and api link
                target = soup.find('video')
                target = target.get('data-apireq')
                links = 'd='+target

            return FileNameClean(title), links

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

    def Download_Request(site, downloadPath):
        #path
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

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