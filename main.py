# vim:fileencoding=utf-8
import os, sys
import urllib, urllib2
import json



class SimpleTumblr(object):
    API_BASE_URL = 'http://api.tumblr.com/v2/'
    def __init__(self, consumer_key):
        self._consumer_key = consumer_key
        
    def api_query(self, url):
        sc = urllib2.urlopen(url)
        data = sc.read()
        sc.close()
        obj = json.loads(data)
        return obj
        
    def api_blog(self, host_name, method, params={}):
        url = self.API_BASE_URL+'blog/'+host_name+'/'+method
        params['api_key'] = self._consumer_key
        param_encoded = urllib.urlencode(params)
        url = url+'?'+param_encoded
        return self.api_query(url)
        
    def api_blog_posts(self, host_name, posttype=None, params={}):
        method = 'posts' + ( '/'+posttype if posttype else '' )
        return self.api_blog(host_name, method, params)
    
def save_json(fname, data):
    sdata = json.dumps(data)
    try:
        f = open(fname, 'w')
        f.write(sdata)
        f.close()
    except IOError:
        sys.exit('An error occured when saving the file: '+fname)
        
def load_json(fname):
    if os.path.isfile(fname):
        try:
            f = open(fname, 'r')
            sdata = f.read()
            f.close()
            return json.loads(sdata)
        except IOError:
            sys.exit('An error occured when loading the file: '+fname)
    else:
        return {}
    
def get_fname_extension(ctype):
    if ctype=='image/gif':
        return '.gif'
    elif ctype=='image/jpeg':
        return '.jpg'
    elif ctype=='image/x-png' or 'image/png':
        return '.png'
    else:
        return ''
        
def download_image(src, dest_dir, base_fname):
    try:
        sc = urllib2.urlopen(src)
        ctype = sc.info().get('content-type')
        data = sc.read()
        sc.close()
    except urllib2.HTTPError:
        sys.stderr.write("Failed to getting images")
        return False
    else:
        try:
            if ctype:
                ext = get_fname_extension(ctype)
            else:
                head,ext = os.path.splitext(src)
            dest = dest_dir + '/' + base_fname + ext
                
            f = open(dest, 'w')
            f.write(data)
            f.close()
            return True
        except IOError:
            sys.exit('An error occured when saving image file.')
            
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_FILE_DIR = ROOT_DIR+'/img'
LOG_FILE_NAME = ROOT_DIR+'/log.json'
SETTING_FILE_NAME = ROOT_DIR+'/setting.json'


if __name__ == '__main__':
    
    print 'loading setting'
    setting = load_json(SETTING_FILE_NAME)
    try:
        consumer_key = setting['consumer_key']
        blogs = setting['blogs']
    except KeyError:
        sys.exit('setting file has some errors.')
    
    tumblr = SimpleTumblr(consumer_key)
    
    print 'loading log'
    log = load_json(LOG_FILE_NAME)
    histories = log.setdefault('histories', {})
    
    url_list = {}
    for blog_domain in blogs:
        history = histories.setdefault(blog_domain, [])
        if len(history)>0:
            recent = history[-1]
            last_id = recent['last_id']
        else:
            last_id = 0
        limit = 20 # 20 is max
        offset = 0
        urls = {}
        try:
            #get url list of photo from tumblr
            print 'getting photo url list: '+blog_domain
            do_next = True
            while(do_next):
                do_next = False
                print 'requesting tumblr api'
                result = tumblr.api_blog_posts(blog_domain, 'photo', {'limit':limit, 'offset':offset})['response']['posts']
                if result:
                    for post in result:
                        if post['id'] > last_id:
                            urls[post['id']] = [photo['original_size']['url'] for photo in post['photos'] ]
                        else:
                           break
                    else:
                        #get next page
                        offset += limit
                        do_next = True
                        
        except urllib2.HTTPError:
            sys.stderr.write("Failed to getting posts from tumblr")
        else:
            dest = IMG_FILE_DIR+'/'+blog_domain
            try:
                if not os.path.isdir(dest):
                    os.makedirs(dest)
            except OSError:
                sys.exit('failed to make the directory for saving images')
            #download images
            cnt = 0
            for post_id, photos in urls.iteritems():
                if len(photos)>1:
                    for i,photo_url in enumerate(photos):
                        base_fname = str(post_id)+'-'+str(i) # append photo index
                        print 'downloading :' + photo_url
                        download_image(photo_url, dest, base_fname)
                        cnt += 1
                else:
                    photo_url = photos[0]
                    base_fname = str(post_id)
                    print 'downloading :' + photo_url
                    download_image(photo_url, dest, base_fname)
                    cnt += 1
            #set recent post_id as last_id
            if urls:
                last_id = reversed(sorted(urls.keys())).next()
                
            history.append({
                'last_id': last_id,
                'count': cnt
            })
            print 'finished downloading photo images : ' + blog_domain
    #save logs
    print 'saving log'
    save_json(LOG_FILE_NAME, log)
