import requests
import json
import time
from PIL import Image
from google.cloud import firestore

class GooglePlaces(object):
    def __init__(self, apiKey):
        super(GooglePlaces, self).__init__()
        self.apiKey = apiKey
    
    #ユーザ入力情報から店舗をサーチ
    def search_places_by_coordinate(self, keywords, location, radius, types, price_level_user):
        endpoint_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        places = []
        keyword_search = ''
        #キーワードを検索用文字列に変換
        for n, keyword in enumerate(keywords):
            if n == 0:
                keyword_search = "("+keyword+")"
            else:
                keyword_search = keyword_search + 'OR' +"("+keyword+")"           
        params = {
            'keyword' : keyword_search,
            'location': location,
            'radius': radius,
            'types': types,
            'maxprice' : price_level_user,
            'key': self.apiKey
        }
        print(keyword_search)
        res = requests.get(endpoint_url, params = params)
        results =  json.loads(res.content)
        places.extend(results['results'])
        time.sleep(2)
        while "next_page_token" in results:
            params['pagetoken'] = results['next_page_token'],
            res = requests.get(endpoint_url, params = params)
            results = json.loads(res.content)
            places.extend(results['results'])
            time.sleep(2)
        return places

    #店舗の詳細情報を取得
    def get_place_details(self, place_id, fields):
        endpoint_url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            'placeid': place_id,
            'fields': ",".join(fields),
            'language':'ja',
            'key': self.apiKey
        }
        res = requests.get(endpoint_url, params = params)
        place_details =  json.loads(res.content)
        return place_details

    #店舗の画像情報を取得
    def get_place_img(self, html_attributions, height, width, photo_reference):
        endpoint_url = "https://maps.googleapis.com/maps/api/place/photo"
        params = {
            'html_attributions': html_attributions,
            'height': height,
            'width':width,
            'photo_reference': photo_reference,
            'key': self.apiKey
        }
        res = requests.get(endpoint_url, params = params)
        return res

    #移動距離/時間を取得
    def get_place_distance_time(self, origins, destinations):
        endpoint_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            'origins' : origins,
            'destinations': "place_id:" + destinations,
            'mode':'walking',
            'key': self.apiKey
        }
        res = requests.get(endpoint_url, params = params)
        distance_time = json.loads(res.content)
        return distance_time
    

def restaurant(request):
    
    db = firestore.Client()

    #前回のレストラン検索情報を削除
    docs = db.collection(u'restaurants').stream()
    for doc in docs:
        db.collection(u'restaurants').document(doc.id).delete()
    #googlemap_API設定
    api = GooglePlaces("AIzaSyBQ_HzKvpdKet-T7W5o45Ozsry4clhz-6w")
    #firestoreからuser情報の取得
    user_info_ref = db.collection(u'users').document(u'userA')
    try:
        user_info = user_info_ref.get().to_dict()
        position = "{}, {}".format(str(user_info["position"]["latitude"]),str(user_info["position"]["longtitude"]))  
        keywords = user_info["keywords"]
        price = user_info["price"]
    except google.cloud.exceptions.NotFound:
        user_info = []
        position = []
        keywords = []
        price = 10000
    
    #ユーザ予算情報を5段階に変換
    if price >= 10000:
        price_level_user = 4
    elif price >= 5000:
        price_level_user = 3
    elif price >= 3000:
        price_level_user = 2
    elif price >= 1000:
        price_level_user = 1
    else:
        price_level_user = 0

    #ユーザ情報を元にレストランを探索
    places = api.search_places_by_coordinate(keywords, position, "200", "restaurant", str(price_level_user))
    #places = api.search_places_by_coordinate(keywords, "35.29149,136.79922", "100", "restaurant")
    fields = ['name', 'formatted_address', 'international_phone_number', 'website', 'rating', 'review', 'photos', 'opening_hours', 'price_level']
    i = 0
    for place in places:
        img=[]
        j=0
        details = api.get_place_details(place['place_id'], fields)
        try:
            website = details['result']['website']
        except KeyError:
            website = ""
 
        try:
            name = details['result']['name']
        except KeyError:
            name = ""
 
        try:
            address = details['result']['formatted_address']
        except KeyError:
            address = ""
 
        try:
            phone_number = details['result']['international_phone_number']
        except KeyError:
            phone_number = ""
 
        try:
            reviews = details['result']['reviews']
        except KeyError:
            reviews = []

        try:
            photos = details['result']['photos']
        except KeyError:
            photos = []
        for photo in photos:
            j=j+1
            img.append("https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={}&key=AIzaSyBQ_HzKvpdKet-T7W5o45Ozsry4clhz-6w".format(photo["photo_reference"]))
        
        try:
            opening_hours = details['result']['opening_hours']
        except KeyError:
            opening_hours = []

        try:
            rating = float(details['result']['rating'])
        except KeyError:
            rating = 5.0

        try:
            price_level = float(details['result']['price_level'])
        except KeyError:
            price_level = -1

        try:
            distance_time = api.get_place_distance_time(position, place['place_id'])
            distance = distance_time["rows"][0]['elements'][0]['distance']['text']
            duration = distance_time["rows"][0]['elements'][0]['duration']['text']
        except KeyError:
            distance_time = []
            distance = 0
            duration = 0
        
        #探索結果をfirestoreに格納
        if 'open_now' in opening_hours and opening_hours['open_now'] == True and rating > 3.5:
            doc_ref = db.collection(u'restaurants').document(details['result']['name'])
            doc_ref.set({
                u'website': website,
                u'address': address,
                u'phone_number': phone_number,
                u'reviews' : reviews,
                u'photos': img,
                u'price_level': price_level,
                u'distance': distance,
                u'duration': duration,
                u'place_id': place['place_id'],
                u'rating' : rating          
            })
            i=i+1
        
    
    print("{}restrants found".format(i))