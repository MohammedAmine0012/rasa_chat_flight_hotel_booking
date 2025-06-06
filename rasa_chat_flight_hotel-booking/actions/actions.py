from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import logging

logger = logging.getLogger(__name__)

class ActionSearchFlights(Action):
    def __init__(self):
        self.airline_names = {
            'SU': 'Aeroflot',
            'TK': 'Turkish Airlines',
            'QR': 'Qatar Airways',
            'EK': 'Emirates',
            'EY': 'Etihad Airways',
            'LH': 'Lufthansa',
            'AF': 'Air France',
            'BA': 'British Airways',
            'AA': 'American Airlines',
            'DL': 'Delta Air Lines',
            'UA': 'United Airlines',
            'AT': 'Royal Air Maroc'
        }
        
        # City to IATA code mapping
        self.city_to_iata = {
            'الرباط': 'RBA',
            'الدار البيضاء': 'CMN',
            'مراكش': 'RAK',
            'فاس': 'FEZ',
            'أكادير': 'AGA',
            'طنجة': 'TNG',
            'وجدة': 'OUD',
            'الناظور': 'NDR',
            'العيون': 'EUN',
            'الداخلة': 'VIL',
            'باريس': 'PAR',
            'لندن': 'LON',
            'مدريد': 'MAD',
            'روما': 'ROM',
            'برشلونة': 'BCN',
            'فرانكفورت': 'FRA',
            'امستردام': 'AMS',
            'بروكسل': 'BRU',
            'جنيف': 'GVA',
            'زيورخ': 'ZRH',
            'فيينا': 'VIE',
            'اسطنبول': 'IST',
            'دبي': 'DXB',
            'أبو ظبي': 'AUH',
            'الدوحة': 'DOH',
            'القاهرة': 'CAI',
            'جدة': 'JED',
            'الرياض': 'RUH',
            'الكويت': 'KWI',
            'بيروت': 'BEY',
            'تونس': 'TUN',
            'الجزائر': 'ALG',
            'نيويورك': 'NYC',
            'لوس أنجلوس': 'LAX',
            'شيكاغو': 'CHI',
            'ميامي': 'MIA',
            'هونغ كونغ': 'HKG',
            'سنغافورة': 'SIN',
            'بانكوك': 'BKK',
            'طوكيو': 'TYO',
            'سيدني': 'SYD'
        }
        
        self.usd_to_mad = 10.0  # Example conversion rate

    def name(self) -> Text:
        return "action_search_flights"

    def convert_to_mad(self, price_usd: float) -> float:
        return round(price_usd * self.usd_to_mad, 2)

    def search_flights_travelpayouts(self, origin: str, destination: str, depart_date: str, trip_class: int = 0) -> Dict:
        try:
            origin_iata = self.city_to_iata.get(origin)
            destination_iata = self.city_to_iata.get(destination)
            
            if not origin_iata or not destination_iata:
                logger.error(f"Invalid city names - Origin: {origin}, Destination: {destination}")
                return {"error": "Invalid city names", "data": []}
            
            params = {
                'currency': 'USD',
                'origin': origin_iata,
                'destination': destination_iata,
                'token': TRAVELPAYOUTS_TOKEN,
                'trip_class': str(trip_class),
                'limit': 10,
                'depart_date': depart_date,
                'market': 'us',
                'locale': 'en'
            }
            
            logger.info(f"Making API request with params: {params}")
            response = requests.get(TRAVELPAYOUTS_BASE_URL + '/prices/latest', params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('success'):
                logger.error(f"API error response: {data}")
                return {"error": data.get('error', 'Unknown error'), "data": []}
            
            return {"data": data.get('data', [])}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching flights: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"API error response: {e.response.text}")
            return {"error": str(e), "data": []}
        except Exception as e:
            logger.error(f"Error in search_flights_travelpayouts: {str(e)}")
            return {"error": str(e), "data": []}

    def format_flight_results(self, flights_data: Dict) -> Tuple[Text, List[Dict]]:
        requested_date = None
        user_selected_class = "اقتصادية"
        try:
            tracker = Tracker.current_tracker
            requested_date = tracker.get_slot("date_depart")
            user_selected_class = tracker.get_slot("classe") or "اقتصادية"
        except Exception:
            pass

        if not flights_data.get('data'):
            return "عذراً، لم يتم العثور على رحلات متاحة لهذا المسار أو التاريخ.", []
        flights = flights_data['data']
        if not flights:
            return "عذراً، لم يتم العثور على رحلات متاحة لهذا المسار أو التاريخ.", []

        date_found = False
        if requested_date:
            for flight in flights:
                if flight.get('depart_date') == requested_date:
                    date_found = True
                    break

        message = f"تم العثور على الرحلات التالية (درجة {user_selected_class}):\n"
        if requested_date and not date_found:
            message += "⚠️ ملاحظة: لم يتم العثور على رحلات للتاريخ المطلوب. تم عرض أقرب الرحلات المتاحة.\n"

        flight_details = []
        arabic_months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        def format_date(date_str):
            try:
                y, m, d = date_str.split('-')
                m = arabic_months[int(m)-1]
                return f"{int(d)} {m} {y}"
            except:
                return date_str
        def format_duration(minutes):
            h = int(minutes) // 60
            m = int(minutes) % 60
            return f"{h} ساعة و {m} دقيقة"

        for idx, flight in enumerate(flights[:10], 1):
            if not flight.get('value') or flight.get('value', 0) == 0:
                continue
            airline = flight.get('gate', 'غير معروف')
            depart_date = format_date(flight.get('depart_date', 'غير معروف'))
            return_date = format_date(flight.get('return_date', 'غير معروف'))
            duration = format_duration(flight.get('duration', 0))
            stops = flight.get('number_of_changes', 0)
            price_mad = f"{self.convert_to_mad(flight.get('value', 0)):.2f} درهم مغربي"
            flight_details.append({
                'airline': airline,
                'departure_time': depart_date,
                'arrival_time': return_date,
                'duration': duration,
                'stops': stops,
                'price_mad': price_mad
            })
            message += f"الرحلة {idx}:\n"
            message += f"الشركة: {airline}\n"
            message += f"تاريخ المغادرة: {depart_date}\n"
            message += f"تاريخ العودة: {return_date}\n"
            message += f"مدة الرحلة: {duration}\n"
            message += f"عدد التوقفات: {stops}\n"
            message += f"السعر: {price_mad}\n"
        if not flight_details:
            return "عذراً، لم يتم العثور على رحلات متاحة لهذا المسار أو التاريخ.", []
        message += "لاختيار رحلة، قل 'الخيار رقم X' حيث X هو رقم الرحلة.\n"
        message += "💡 يمكنك طلب البحث عن تاريخ آخر بقول 'غير التاريخ'"
        return message, flight_details

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            origin = tracker.get_slot("ville_depart")
            destination = tracker.get_slot("ville_destination")
            depart_date = tracker.get_slot("date_depart")
            trip_class = tracker.get_slot("classe")
            
            if not all([origin, destination, depart_date]):
                dispatcher.utter_message(text="عذراً، يرجى تحديد جميع المعلومات المطلوبة (المغادرة، الوجهة، التاريخ).")
                return []
            
            trip_class_map = {
                'اقتصادية': 0,
                'أعمال': 1,
                'أولى': 2
            }
            trip_class_value = trip_class_map.get(trip_class, 0)
            
            logger.info(f"Flight search: {origin} -> {destination} on {depart_date} ({trip_class})")
            
            flights_data = self.search_flights_travelpayouts(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                trip_class=trip_class_value
            )
            
            if 'error' in flights_data:
                dispatcher.utter_message(text=f"عذراً، حدث خطأ أثناء البحث عن الرحلات: {flights_data['error']}")
                return []
            
            message, flight_details = self.format_flight_results(flights_data)
            dispatcher.utter_message(text=message)
            
            return [
                SlotSet("flight_details", flight_details),
                SlotSet("search_completed", True)
            ]
            
        except Exception as e:
            logger.error(f"Error in ActionSearchFlights: {str(e)}")
            dispatcher.utter_message(text="عذراً، حدث خطأ أثناء البحث عن الرحلات. يرجى المحاولة مرة أخرى.")
            return []