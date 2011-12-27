# vim:fileencoding=utf-8
import os, sys, getopt
import urllib, urllib2
import json
import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_FILE_DIR = ROOT_DIR+'/img'
SETTING_FILE_NAME = ROOT_DIR+'/config.json'


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

class Config(object):
    def __init__(self):
        self.fname = SETTING_FILE_NAME
        self.consumer_key = None
        self.blogs = []

    def load(self):

        f = open( self.fname, 'r' )
        sdata = f.read()
        f.close()
        data = json.loads(sdata)


        self.blogs = []
        if 'blogs' in data:
            for domain in data['blogs']:
                self.blogs.append( domain )

        if 'api' in data:
            if 'consumer_key' in data['api']:
                self.consumer_key = data['api']['consumer_key']

        return True


class Log(object):
    def __init__(self, posts=None, last_id=None, created=None):
        self.posts = posts or {}
        self.last_id = last_id
        self.created = created or datetime.datetime.now().replace(microsecond=0)

    def add_post(self, post):
        self.posts[post.id] = post

    @staticmethod
    def create_from_log(logdata):
        log = Log()
        if 'posts' in logdata:
            for post_id, postdata in logdata['posts'].iteritems():
                log.add_post( DownloadPost.create_from_log(postdata) )
        log.last_id = logdata['last_id']
        log.created = datetime.datetime.strptime(logdata['created'], '%Y-%m-%d %H:%M:%S')
        return log

    def dump_log(self):
        data = {}
        data['posts'] = {}
        for post_id, post in self.posts.iteritems():
            data['posts'][post_id] = post.dump_log()
        data['last_id'] = self.last_id
        data['created'] = self.created.isoformat(' ')
        return data



class DownloadPost(object):
    def __init__(self):
        pass

    @staticmethod
    def create_from_apidata(postdata):
        post = DownloadPost()
        post.id = postdata['id']
        post.urls = set( photo['original_size']['url'] for photo in postdata['photos'] )
        post.states = dict.fromkeys(post.urls, 'not yet')
        return post

    @staticmethod
    def create_from_log(postdata):
        post = DownloadPost()
        post.id = postdata['id']
        post.urls = set( postdata['urls'] )
        post.states = postdata['states']
        return post

    def dump_log(self):
        data = {}
        data['id'] = self.id
        data['urls'] = list(self.urls)
        data['states'] = self.states
        return data


class Logs(object):
    def __init__(self, domain):
        self.domain = domain
        self.fname = ROOT_DIR+'/'+domain+'.log.json'
        self.current = None
        self.histories = []

    def init_current(self):
        self.current = Log()

    def push_current(self):
        if self.current:
            self.histories.append( self.current )
            self.current = None

    def load(self):
        if os.path.isfile( self.fname ):
            f = open( self.fname, 'r' )
            sdata = f.read()
            f.close()
            data = json.loads(sdata)

            if 'histories' in data:
                self.histories = [ Log.create_from_log(logdata) for logdata in data['histories'] ]
            else:
                self.histories = []

    def save(self):
        data = {}
        data['domain'] = self.domain
        data['histories'] = [ log.dump_log() for log in self.histories ]

        sdata = json.dumps(data)
        f = open( self.fname, 'w' )
        f.write(sdata)
        f.close()


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
    sc = urllib2.urlopen(src)
    ctype = sc.info().get('content-type')
    data = sc.read()
    sc.close()

    if ctype:
        ext = get_fname_extension(ctype)
    else:
        head,ext = os.path.splitext(src)
    dest = dest_dir + '/' + base_fname + ext

    f = open(dest, 'w')
    f.write(data)
    f.close()


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['blog=', 'last_id='])
    except getopt.GetoptError, e:
        sys.stderr.write( str(e) )
        sys.exit(2)
    
    opt_blog = None
    opt_last_id = None
    for o, v in opts:
        if o == '--blog':
            opt_blog = v
        elif o == '--last_id':
            for _o, _v in opts:
                if _o == '--blog':
                    opt_last_id = v
                    break
            else:
                sys.stderr.write( 'If you specify last_id of downloading posts, you need specify the blog domain too as option' )
                sys.exit(2)


    print 'loading config'
    config = Config()
    config.load()
    consumer_key = config.consumer_key

    tumblr = SimpleTumblr(consumer_key)

    if opt_blog is None:
        blogs = config.blogs
    else:
        blogs = [opt_blog]

    print 'start downloading'

    for blog_domain in blogs:

        print 'loading a log of %s' % blog_domain
        #load logs
        logs = Logs(blog_domain)
        logs.load()
        logs.init_current()
        if opt_last_id is None:
            if len(logs.histories)>0:
                recent = logs.histories[-1]
                last_id = int(recent.last_id)
            else:
                last_id = 0
        else:
            last_id = int(opt_last_id)


        limit = 20 # 20 is max
        offset = 0

        #check the dest directory
        dest = IMG_FILE_DIR+'/'+blog_domain
        try:
            if not os.path.isdir(dest):
                os.makedirs(dest)
        except OSError:
            sys.exit('failed to make the directory for saving images')

        do_next = True
        #repeat requesting until post_id in the api results exceeds the last_id
        while(do_next):
            #get url list of photo from tumblr
            do_next = False
            posts = []
            print 'requesting to tumblr api'
            result = tumblr.api_blog_posts(blog_domain, 'photo', {'limit':limit, 'offset':offset})['response']['posts']
            if result:
                for postdata in result:
                    if int(postdata['id']) > last_id:
                        posts.append( DownloadPost.create_from_apidata(postdata) )
                    else:
                       break
                else:
                    #ready for getting the next page
                    offset += limit
                    do_next = True

            #download images
            print 'starting to download photos'
            for post in posts:
                for i,photo_url in enumerate(post.urls):
                    if len(post.urls)>1:
                        base_fname = str(post.id)+'-'+str(i) # append photo index
                    else:
                        base_fname = str(post.id)
                    print 'downloading :' + photo_url
                    try:
                        dlresult = download_image(photo_url, dest, base_fname)
                    except Exception,e:
                        print e
                        post.states[photo_url] = 'failed'
                    else:
                        post.states[photo_url] = 'success'

                #add current log
                logs.current.add_post( post )

        #set the recent post_id as last_id
        if logs.current.posts:
            last_id = max(logs.current.posts.keys())
        logs.current.last_id = last_id
        print 'finished downloading photo images : ' + blog_domain
        #save logs
        print 'saving the log'
        logs.push_current()
        logs.save()

    print 'complete downloading'
