from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
import logging
import requests
from datetime import datetime, timedelta
import json
import re
from rasa_sdk.events import SlotSet
from config.api_config import RAPIDAPI_KEY, API_HOST, CITY_MAPPING

logger = logging.getLogger(__name__)

# TravelPayouts API Configuration
TRAVELPAYOUTS_TOKEN = "f5f51cb0da31f68c244d98f5e989a9c1"
TRAVELPAYOUTS_BASE_URL = "https://api.travelpayouts.com/v2"

# المدن المغربية المدعومة
MOROCCAN_CITIES = [
    'الرباط', 'الدار البيضاء', 'الدارالبيضاء', 'مراكش', 'فاس', 
    'أكادير', 'طنجة', 'وجدة', 'تطوان', 'الحسيمة', 'القنيطرة', 'سلا'
]

# الوجهات الدولية المدعومة
INTERNATIONAL_DESTINATIONS = [
    "باريس", "لندن", "مدريد", "دبي", "القاهرة", "تونس",
    "إسطنبول", "روما", "برلين", "أمستردام", "بروكسل", "نيويورك",
    "تورنتو", "مونتريال", "جنيف", "زيوريخ", "لوس أنجلوس"
]

class ValidateFlightForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_flight_form"

    def validate_ville_depart(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        logger.info(f"Validating ville_depart: slot_value={slot_value}")
        
        # استخراج اسم المدينة من entities
        city = None
        entities = tracker.latest_message.get('entities', [])
        
        logger.info(f"Available entities: {entities}")
        
        # البحث عن أي entity يحتوي على مدينة مغربية أو وجهة دولية
        for entity in entities:
            entity_value = entity.get('value', '')
            entity_type = entity.get('entity', '')
            logger.info(f"Checking entity: {entity_value} (type: {entity_type})")
            
            if (any(moroccan_city in entity_value for moroccan_city in MOROCCAN_CITIES) or
                any(dest in entity_value for dest in INTERNATIONAL_DESTINATIONS)):
                city = entity_value
                logger.info(f"Found city in entity: {city}")
                break
        
        # إذا لم نجد في entities، نستخدم slot_value
        if not city and slot_value:
            city = slot_value
            logger.info(f"Using slot_value as city: {city}")
            
        if city and (any(moroccan_city in city for moroccan_city in MOROCCAN_CITIES) or
                    any(dest in city for dest in INTERNATIONAL_DESTINATIONS)):
            logger.info(f"Valid departure city detected: {city}")
            return {"ville_depart": city}
        else:
            dispatcher.utter_message(
                text="عذراً، يرجى اختيار مدينة صحيحة للمغادرة.\n"
                     "المدن المغربية المتاحة: الرباط، الدار البيضاء، مراكش، فاس، أكادير، طنجة\n"
                     "الوجهات الدولية المتاحة: باريس، لندن، مدريد، دبي، نيويورك، لوس أنجلوس، وغيرها"
            )
            return {"ville_depart": None}

    def validate_ville_destination(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        logger.info(f"Validating ville_destination: slot_value={slot_value}")
        
        # استخراج اسم المدينة من entities
        city = None
        entities = tracker.latest_message.get('entities', [])
        logger.info(f"Available entities: {entities}")
        
        # First try to find the city in entities
        for entity in entities:
            entity_value = entity.get('value', '')
            entity_type = entity.get('entity', '')
            logger.info(f"Checking entity: {entity_value} (type: {entity_type})")
            
            # Check both international destinations and Moroccan cities
            if (any(dest in entity_value for dest in INTERNATIONAL_DESTINATIONS) or
                any(moroccan_city in entity_value for moroccan_city in MOROCCAN_CITIES)):
                city = entity_value
                logger.info(f"Found destination city in entity: {city}")
                break
        
        # If no city found in entities, try the slot_value
        if not city and slot_value:
            city = slot_value
            logger.info(f"Using slot_value as city: {city}")
            
            # Check if the slot_value matches any known city
            if (any(dest in city for dest in INTERNATIONAL_DESTINATIONS) or
                any(moroccan_city in city for moroccan_city in MOROCCAN_CITIES)):
                logger.info(f"Valid destination city detected in slot_value: {city}")
                return {"ville_destination": city}
        
        if city:
            logger.info(f"Valid destination city detected: {city}")
            return {"ville_destination": city}
        else:
            dispatcher.utter_message(
                text="يرجى تحديد مدينة الوجهة.\n"
                     "الوجهات المتاحة: باريس، لندن، مدريد، دبي، القاهرة، تونس، إسطنبول، نيويورك، وغيرها"
            )
            return {"ville_destination": None}

    def validate_date_depart(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if not slot_value:
            dispatcher.utter_message(text="متى تريد السفر؟")
            return {"date_depart": None}

        # Handle Arabic date formats
        try:
            # Convert Arabic numbers to English
            arabic_to_english = {
                '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
                '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
            }
            date_text = slot_value
            for arabic, english in arabic_to_english.items():
                date_text = date_text.replace(arabic, english)

            # Handle special cases
            if 'غداً' in date_text or 'غدا' in date_text:
                tomorrow = datetime.now() + timedelta(days=1)
                formatted_date = tomorrow.strftime("%Y-%m-%d")
                return {"date_depart": formatted_date}
            
            if 'بعد غد' in date_text:
                day_after_tomorrow = datetime.now() + timedelta(days=2)
                formatted_date = day_after_tomorrow.strftime("%Y-%m-%d")
                return {"date_depart": formatted_date}

            # Handle "next week"
            if 'الأسبوع القادم' in date_text:
                next_week = datetime.now() + timedelta(days=7)
                formatted_date = next_week.strftime("%Y-%m-%d")
                return {"date_depart": formatted_date}

            # Handle regular date format (e.g., "15 مايو" or "15 mai")
            arabic_months = {
                'يناير': '01', 'فبراير': '02', 'مارس': '03', 'أبريل': '04',
                'مايو': '05', 'يونيو': '06', 'يوليو': '07', 'أغسطس': '08',
                'سبتمبر': '09', 'أكتوبر': '10', 'نوفمبر': '11', 'ديسمبر': '12',
                'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
                'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
                'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
            }

            # Extract day and month
            match = re.search(r'(\d+)\s+(\w+)', date_text)
            if match:
                day = match.group(1)
                month_arabic = match.group(2)
                
                if month_arabic in arabic_months:
                    month = arabic_months[month_arabic]
                    year = datetime.now().year
                    
                    # Check if the date is in the past
                    try:
                        date_obj = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                        if date_obj < datetime.now():
                            year += 1  # If date is in the past, assume next year
                        
                        formatted_date = f"{year}-{month}-{day.zfill(2)}"
                        return {"date_depart": formatted_date}
                    except ValueError:
                        pass

            dispatcher.utter_message(
                text="عذراً، يرجى تحديد تاريخ صحيح للسفر.\n"
                     "مثال: 15 مايو، غداً، الأسبوع القادم"
            )
            return {"date_depart": None}

        except Exception as e:
            logger.error(f"Error processing date: {str(e)}")
            dispatcher.utter_message(
                text="عذراً، يرجى تحديد تاريخ صحيح للسفر.\n"
                     "مثال: 15 مايو، غداً، الأسبوع القادم"
            )
            return {"date_depart": None}

    def validate_classe(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        if slot_value:
            slot_value_clean = slot_value.strip().lower()
            
            # تنظيف وتوحيد الإجابات
            if any(classe in slot_value_clean for classe in ["اقتصادية", "عادية", "عاديه", "economy", "eco"]):
                logger.info("Selected economy class")
                return {"classe": "اقتصادية"}
            elif any(classe in slot_value_clean for classe in ["أعمال", "بزنس", "business"]):
                logger.info("Selected business class")
                return {"classe": "أعمال"}
            elif any(classe in slot_value_clean for classe in ["أولى", "فاخرة", "first", "فيرست"]):
                logger.info("Selected first class")
                return {"classe": "أولى"}
            else:
                dispatcher.utter_message(text="الدرجات المتاحة: اقتصادية، أعمال، أولى")
                return {"classe": None}
        else:
            dispatcher.utter_message(text="أي درجة تفضل؟ (اقتصادية، أعمال، أولى)")
            return {"classe": None}

class ValidateHotelForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_hotel_form"

    def validate_ville_hotel(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        logger.info(f"Validating ville_hotel: slot_value={slot_value}")
        
        # استخراج اسم المدينة من entities
        city = None
        entities = tracker.latest_message.get('entities', [])
        
        for entity in entities:
            entity_value = entity.get('value', '')
            if any(moroccan_city in entity_value for moroccan_city in MOROCCAN_CITIES) or \
               any(dest in entity_value for dest in INTERNATIONAL_DESTINATIONS):
                city = entity_value
                logger.info(f"Found hotel city in entity: {city}")
                break
                
        if not city and slot_value:
            city = slot_value
            
        if city and (any(moroccan_city in city for moroccan_city in MOROCCAN_CITIES) or \
                    any(dest in city for dest in INTERNATIONAL_DESTINATIONS)):
            logger.info(f"Valid hotel city detected: {city}")
            return {"ville_hotel": city}
        else:
            dispatcher.utter_message(
                text="عذراً، يرجى اختيار مدينة صحيحة للإقامة.\n\n"
                     "المدن المغربية المتاحة:\n"
                     "الرباط، الدار البيضاء، مراكش، فاس، أكادير، طنجة\n\n"
                     "الوجهات الدولية المتاحة:\n"
                     "باريس، لندن، مدريد، دبي، نيويورك، لوس أنجلوس، وغيرها"
            )
            return {"ville_hotel": None}

    def validate_categorie_hotel(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        if slot_value:
            slot_value_clean = slot_value.strip()
            
            # تنظيف الإجابة وتوحيدها
            if any(x in slot_value_clean for x in ["3", "ثلاث", "3 نجوم", "ثلاث نجوم"]):
                logger.info("Selected 3-star hotel")
                return {"categorie_hotel": "3 نجوم"}
            elif any(x in slot_value_clean for x in ["4", "أربع", "4 نجوم", "أربع نجوم"]):
                logger.info("Selected 4-star hotel")
                return {"categorie_hotel": "4 نجوم"}
            elif any(x in slot_value_clean for x in ["5", "خمس", "5 نجوم", "خمس نجوم"]):
                logger.info("Selected 5-star hotel")
                return {"categorie_hotel": "5 نجوم"}
            elif any(x in slot_value_clean for x in ["فاخر", "luxury"]):
                logger.info("Selected luxury hotel")
                return {"categorie_hotel": "فاخر"}
            else:
                dispatcher.utter_message(text="الفئات المتاحة: 3 نجوم، 4 نجوم، 5 نجوم، فاخر")
                return {"categorie_hotel": None}
        else:
            dispatcher.utter_message(text="كم نجمة تريد للفندق؟ (3، 4، 5 نجوم)")
            return {"categorie_hotel": None}
            
    def validate_nombre_personnes(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        if slot_value:
            logger.info(f"Valid number of persons: {slot_value}")
            return {"nombre_personnes": slot_value}
        else:
            dispatcher.utter_message(text="كم عدد الأشخاص؟ مثال: شخصين، 4 أشخاص")
            return {"nombre_personnes": None}

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
            # Moroccan cities
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
            
            # International cities
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
            # Convert city names to IATA codes
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
        # Assume self.requested_date and self.user_selected_class are set if needed
        requested_date = None
        user_selected_class = "اقتصادية"
        # Try to get requested date from tracker if available
        try:
            from rasa_sdk import Tracker
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

        # Check if any flight matches the requested date
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
            # Get slot values
            origin = tracker.get_slot("ville_depart")
            destination = tracker.get_slot("ville_destination")
            depart_date = tracker.get_slot("date_depart")
            trip_class = tracker.get_slot("classe")
            
            if not all([origin, destination, depart_date]):
                dispatcher.utter_message(text="عذراً، يرجى تحديد جميع المعلومات المطلوبة (المغادرة، الوجهة، التاريخ).")
                return []
            
            # Convert trip class to numeric value
            trip_class_map = {
                'اقتصادية': 0,
                'أعمال': 1,
                'أولى': 2
            }
            trip_class_value = trip_class_map.get(trip_class, 0)
            
            logger.info(f"Flight search: {origin} -> {destination} on {depart_date} ({trip_class})")
            
            # Search for flights
            flights_data = self.search_flights_travelpayouts(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                trip_class=trip_class_value
            )
            
            if 'error' in flights_data:
                dispatcher.utter_message(text=f"عذراً، حدث خطأ أثناء البحث عن الرحلات: {flights_data['error']}")
                return []
            
            # Format and send results
            message, flight_details = self.format_flight_results(flights_data)
            dispatcher.utter_message(text=message)
            
            # Store flight details in slots for later use
            return [
                SlotSet("flight_details", flight_details),
                SlotSet("search_completed", True)
            ]
            
        except Exception as e:
            logger.error(f"Error in ActionSearchFlights: {str(e)}")
            dispatcher.utter_message(text="عذراً، حدث خطأ أثناء البحث عن الرحلات. يرجى المحاولة مرة أخرى.")
            return []

class ActionSearchHotels(Action):
    def name(self) -> Text:
        return "action_search_hotels"

    def translate_review_score(self, score_word: str) -> str:
        """Translate review score words from French to Arabic."""
        translations = {
            "Très bien": "ممتاز",
            "Bien": "جيد",
            "Satisfaisant": "مقبول",
            "Décevant": "مخيب للأمل",
            "Médiocre": "ضعيف",
            "Mauvais": "سيء",
            "Très mauvais": "سيء جداً"
        }
        return translations.get(score_word, score_word)

    def format_review_score(self, score: float, score_word: str) -> str:
        """Format the review score in Arabic."""
        if not score or score == "None":
            return "لا يوجد تقييم"
        
        try:
            score_float = float(score)
            score_word_ar = self.translate_review_score(score_word)
            return f"{score_float:.1f}/10 - {score_word_ar}"
        except (ValueError, TypeError):
            return "لا يوجد تقييم"

    def convert_arabic_number(self, text: str) -> int:
        """Convert Arabic number text to integer."""
        arabic_to_number = {
            'شخص': 1,
            'شخصين': 2,
            'ثلاثة أشخاص': 3,
            'أربعة أشخاص': 4,
            'خمسة أشخاص': 5,
            'ستة أشخاص': 6,
            'سبعة أشخاص': 7,
            'ثمانية أشخاص': 8,
            'تسعة أشخاص': 9,
            'عشرة أشخاص': 10
        }
        return arabic_to_number.get(text, 2)  # Default to 2 if not found

    def get_destination_id(self, city_name: str) -> str:
        """Get the destination ID for a city from Booking.com API."""
        url = f"https://{API_HOST}/v1/hotels/locations"
        params = {"name": city_name, "locale": "fr"}
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": API_HOST
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                raise ValueError("No destination data returned")
            return data[0]["dest_id"]
        except Exception as e:
            logger.error(f"Error getting destination ID: {str(e)}")
            raise

    def search_hotels(self, dest_id: str, adults: int = 2, stars: str = None) -> List[Dict]:
        """Search for hotels using Booking.com API."""
        url = f"https://{API_HOST}/v1/hotels/search"
        
        # Set check-in date to tomorrow and check-out to day after tomorrow
        checkin_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        checkout_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        params = {
            "checkin_date": checkin_date,
            "checkout_date": checkout_date,
            "dest_type": "city",
            "dest_id": dest_id,
            "adults_number": adults,
            "locale": "fr",
            "order_by": "price",
            "units": "metric",
            "room_number": "1",
            "currency": "MAD",
            "filter_by_currency": "MAD",
            "page_number": "0"
        }
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": API_HOST
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            hotels = data.get("result", [])
            
            # Filter by stars if specified
            if stars:
                star_count = int(stars.split()[0])  # Extract number from "3 نجوم"
                hotels = [h for h in hotels if h.get("class") == star_count]
            
            return hotels[:3]  # Return top 3 hotels
        except Exception as e:
            logger.error(f"Error searching hotels: {str(e)}")
            return []

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        ville_hotel = tracker.get_slot("ville_hotel")
        categorie_hotel = tracker.get_slot("categorie_hotel") 
        nombre_personnes = tracker.get_slot("nombre_personnes")
        
        logger.info(f"Hotel search: {ville_hotel}, {categorie_hotel}, {nombre_personnes} persons")
        
        # Check required information
        if not ville_hotel:
            dispatcher.utter_message(text="أحتاج إلى معرفة المدينة أولاً. في أي مدينة تريد الإقامة؟")
            return []
            
        if not categorie_hotel:
            dispatcher.utter_message(text="أحتاج إلى معرفة فئة الفندق. كم نجمة تريد؟ (3، 4، 5 نجوم)")
            return []
            
        if not nombre_personnes:
            dispatcher.utter_message(text="أحتاج إلى معرفة عدد الأشخاص. كم شخص؟")
            return []
        
        try:
            # Convert Arabic number to integer
            num_persons = self.convert_arabic_number(nombre_personnes)
            
            # Convert Arabic city name to English
            english_city = CITY_MAPPING.get(ville_hotel)
            if not english_city:
                dispatcher.utter_message(text="عذراً، هذه المدينة غير مدعومة حالياً.")
                return []
            
            # Get destination ID
            dest_id = self.get_destination_id(english_city)
            
            # Extract star rating from category
            star_count = None
            if "3" in categorie_hotel:
                star_count = "3"
            elif "4" in categorie_hotel:
                star_count = "4"
            elif "5" in categorie_hotel:
                star_count = "5"
            
            # First try to search with specific star rating
            hotels = self.search_hotels(
                dest_id=dest_id,
                adults=num_persons,
                stars=star_count
            )
            
            # If no hotels found with specific star rating, try without star filter
            if not hotels:
                logger.info(f"No hotels found with {star_count} stars, searching all hotels")
                hotels = self.search_hotels(
                    dest_id=dest_id,
                    adults=num_persons,
                    stars=None
                )
                
                if not hotels:
                    dispatcher.utter_message(
                        text=f"عذراً، لم يتم العثور على فنادق متاحة في {ville_hotel}."
                    )
                    return []
                
                # Show message about showing all available hotels
                dispatcher.utter_message(
                    text=f"لم يتم العثور على فنادق {categorie_hotel} في {ville_hotel}. "
                         f"سأعرض لك جميع الفنادق المتاحة:"
                )
            
            # Format and send results
            message = f"🏨 تم العثور على فنادق في {ville_hotel}\n"
            message += f"👥 عدد الأشخاص: {nombre_personnes}\n"
            message += "\n" + "="*40 + "\n\n"
            
            for i, hotel in enumerate(hotels, 1):
                name = hotel.get("hotel_name", "غير معروف")
                stars = hotel.get("class", "غير معروف")
                area = hotel.get("district", "غير معروف")
                price = hotel.get("min_total_price", "غير معروف")
                review_score = hotel.get("review_score", "غير معروف")
                review_score_word = hotel.get("review_score_word", "")
                
                # Format price to show in MAD
                try:
                    price_mad = float(price) * 10  # Convert to MAD
                    price_display = f"{price_mad:.2f} درهم/ليلة"
                except (ValueError, TypeError):
                    price_display = "غير متوفر"
                
                # Format star rating
                try:
                    stars_display = f"{int(float(stars))} نجوم" if stars and float(stars) > 0 else "غير مصنف"
                except (ValueError, TypeError):
                    stars_display = "غير مصنف"
                
                # Format review score
                review_display = self.format_review_score(review_score, review_score_word)
                
                message += f"🏨 **الخيار {i}: {name}**\n"
                message += f"   💰 السعر: {price_display}\n"
                message += f"   ⭐ التقييم: {stars_display}"
                if review_display != "لا يوجد تقييم":
                    message += f" ({review_display})"
                message += f"\n   📍 الموقع: {area}\n\n"
            
            message += "🔹 أي فندق تفضل؟ قل **'الخيار رقم 1'** أو **'الخيار رقم 2'** أو **'الخيار رقم 3'**"
            
            dispatcher.utter_message(text=message)
            return []
            
        except Exception as e:
            logger.error(f"Error in hotel search: {str(e)}")
            dispatcher.utter_message(
                text="عذراً، حدث خطأ أثناء البحث عن الفنادق. يرجى المحاولة مرة أخرى."
            )
            return []

class ActionSelectOption(Action):
    def name(self) -> Text:
        return "action_select_option"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the latest message
        latest_message = tracker.latest_message.get('text', '')
        
        # Check if we're in flight selection mode
        if tracker.get_slot("ville_depart") and tracker.get_slot("ville_destination"):
            flight_details = tracker.get_slot("flight_details")
            if not flight_details:
                dispatcher.utter_message(text="عذراً، لم يتم العثور على تفاصيل الرحلات. يرجى البحث عن الرحلات أولاً.")
                return []
            
            # Extract the option number
            if "الخيار رقم 1" in latest_message or "الخيار الأول" in latest_message:
                if len(flight_details) > 0:
                    selected_flight = flight_details[0]
                    dispatcher.utter_message(text="تم اختيار الرحلة الأولى. هل تريد تأكيد الحجز؟")
                    return [SlotSet("selected_flight", selected_flight)]
            elif "الخيار رقم 2" in latest_message or "الخيار الثاني" in latest_message:
                if len(flight_details) > 1:
                    selected_flight = flight_details[1]
                    dispatcher.utter_message(text="تم اختيار الرحلة الثانية. هل تريد تأكيد الحجز؟")
                    return [SlotSet("selected_flight", selected_flight)]
            elif "الخيار رقم 3" in latest_message or "الخيار الثالث" in latest_message:
                if len(flight_details) > 2:
                    selected_flight = flight_details[2]
                    dispatcher.utter_message(text="تم اختيار الرحلة الثالثة. هل تريد تأكيد الحجز؟")
                    return [SlotSet("selected_flight", selected_flight)]
            elif "الخيار رقم 4" in latest_message or "الخيار الرابع" in latest_message:
                if len(flight_details) > 3:
                    selected_flight = flight_details[3]
                    dispatcher.utter_message(text="تم اختيار الرحلة الرابعة. هل تريد تأكيد الحجز؟")
                    return [SlotSet("selected_flight", selected_flight)]
            elif "الخيار رقم 5" in latest_message or "الخيار الخامس" in latest_message:
                if len(flight_details) > 4:
                    selected_flight = flight_details[4]
                    dispatcher.utter_message(text="تم اختيار الرحلة الخامسة. هل تريد تأكيد الحجز؟")
                    return [SlotSet("selected_flight", selected_flight)]
            else:
                dispatcher.utter_message(text="عذراً، يرجى اختيار رحلة من القائمة المتاحة (الخيار رقم 1، 2، 3، 4، أو 5)")
                return []
        
        # Check if we're in hotel selection mode
        elif tracker.get_slot("ville_hotel") and tracker.get_slot("categorie_hotel"):
            # Extract the option number
            if "الخيار رقم 1" in latest_message or "الخيار الأول" in latest_message:
                dispatcher.utter_message(text="تم اختيار الفندق الأول. هل تريد تأكيد الحجز؟")
                return [SlotSet("selected_hotel", "الخيار الأول")]
            elif "الخيار رقم 2" in latest_message or "الخيار الثاني" in latest_message:
                dispatcher.utter_message(text="تم اختيار الفندق الثاني. هل تريد تأكيد الحجز؟")
                return [SlotSet("selected_hotel", "الخيار الثاني")]
            elif "الخيار رقم 3" in latest_message or "الخيار الثالث" in latest_message:
                dispatcher.utter_message(text="تم اختيار الفندق الثالث. هل تريد تأكيد الحجز؟")
                return [SlotSet("selected_hotel", "الخيار الثالث")]
            else:
                dispatcher.utter_message(text="عذراً، يرجى قول 'الخيار رقم 1' أو 'الخيار رقم 2' أو 'الخيار رقم 3'")
                return []
        
        dispatcher.utter_message(text="عذراً، لم أفهم اختيارك. يرجى البحث عن رحلات أو فنادق أولاً.")
        return []

class ActionConfirmReservation(Action):
    def name(self) -> Text:
        return "action_confirm_reservation"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the latest message
        latest_message = tracker.latest_message.get('text', '').lower()
        
        # Check if the user confirmed
        if any(word in latest_message for word in ['نعم', 'اي', 'ايوا', 'موافق', 'حسنا']):
            # Get hotel details
            selected_hotel = tracker.get_slot("selected_hotel")
            ville_hotel = tracker.get_slot("ville_hotel")
            categorie_hotel = tracker.get_slot("categorie_hotel")
            nombre_personnes = tracker.get_slot("nombre_personnes")
            
            # Build confirmation message
            message = (
                "🤖 **وكالة السفر الذكية**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎉 تم تأكيد حجزك بنجاح!\n\n"
                f"🏨 **تفاصيل الحجز:**\n"
                f"   📍 المدينة: {ville_hotel}\n"
                f"   ⭐ الفئة: {categorie_hotel}\n"
                f"   👥 عدد الأشخاص: {nombre_personnes}\n"
                f"   🏠 الفندق: {selected_hotel}\n\n"
                "📧 سيتم إرسال تفاصيل الحجز عبر البريد الإلكتروني خلال 10 دقائق\n"
                "احتفظ برقم الحجز للمراجعة\n\n"
                "📱 خدمة العملاء:\n"
                "📞 الهاتف: +212-5XX-XXXXXX\n"
                "💬 واتساب: +212-6XX-XXXXXX\n"
                "⏰ متاح 24/7\n\n"
                "🌟 شكراً لثقتك بوكالة السفر الذكية!"
            )
            
            dispatcher.utter_message(text=message)
            
            # Reset all slots and restart
            return [
                SlotSet("selected_hotel", None),
                SlotSet("ville_hotel", None),
                SlotSet("categorie_hotel", None),
                SlotSet("nombre_personnes", None),
                {"event": "restart"}
            ]
        elif any(word in latest_message for word in ['لا', 'كلا', 'لأ', 'عذراً']):
            dispatcher.utter_message(
                text="تم إلغاء الحجز. هل تريد البحث عن فنادق أخرى؟"
            )
            return [
                SlotSet("selected_hotel", None),
                SlotSet("categorie_hotel", None)
            ]
        else:
            dispatcher.utter_message(
                text="هل تريد تأكيد الحجز؟ قل 'نعم' للتأكيد أو 'لا' للإلغاء"
            )
            return []

class ActionChangeOption(Action):
    def name(self) -> Text:
        return "action_change_option"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # التحقق من نوع الحجز الحالي
        is_flight = bool(tracker.get_slot("ville_depart") or tracker.get_slot("ville_destination"))
        is_hotel = bool(tracker.get_slot("ville_hotel"))
        
        message = "🔄 **لا مشكلة! يمكنك تغيير أي شيء تريده**\n\n"
        
        if is_flight:
            message += "✈️ **للرحلات الجوية، يمكنك تغيير:**\n"
            message += "   📍 مدينة المغادرة - قل 'غير المغادرة'\n"
            message += "   📍 مدينة الوجهة - قل 'غير الوجهة'\n"
            message += "   📅 تاريخ السفر - قل 'غير التاريخ'\n"
            message += "   💺 درجة السفر - قل 'غير الدرجة'\n\n"
            
        if is_hotel:
            message += "🏨 **للفنادق، يمكنك تغيير:**\n"
            message += "   📍 المدينة - قل 'غير المدينة'\n"
            message += "   ⭐ فئة الفندق - قل 'غير الفئة'\n"
            message += "   👥 عدد الأشخاص - قل 'غير العدد'\n\n"
            
        if not is_flight and not is_hotel:
            message += "🎯 **يمكنك بدء حجز جديد:**\n"
            message += "   ✈️ قل 'أريد حجز رحلة طيران'\n"
            message += "   🏨 قل 'أريد حجز فندق'\n\n"
            
        message += "💡 **أو أخبرني مباشرة بما تريد تعديله**"
        
        dispatcher.utter_message(text=message)
        
        # مسح الخيار المحدد لإعطاء المستخدم فرصة جديدة
        return [{"event": "slot", "name": "selected_option", "value": None}]

class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # التحقق من السياق الحالي
        active_form = tracker.active_loop.get('name') if tracker.active_loop else None
        requested_slot = tracker.get_slot('requested_slot')
        
        message = "🤖 **وكالة السفر الذكية**\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if active_form == 'flight_form':
            if requested_slot == 'ville_depart':
                message += "🤔 لم أفهم المدينة. من أي مدينة تريد السفر؟\n"
                message += "المدن المتاحة: الرباط، الدار البيضاء، مراكش، فاس، أكادير، طنجة"
            elif requested_slot == 'ville_destination':
                message += "🤔 لم أفهم الوجهة. إلى أي مدينة تريد السفر؟\n"
                message += "مثال: باريس، لندن، مدريد، دبي"
            elif requested_slot == 'date_depart':
                message += "🤔 لم أفهم التاريخ. متى تريد السفر؟\n"
                message += "مثال: 15 مايو، غداً، الأسبوع القادم"
            elif requested_slot == 'classe':
                message += "🤔 لم أفهم الدرجة. أي درجة تفضل؟\n"
                message += "الخيارات: اقتصادية، أعمال، أولى"
            else:
                message += "🤔 لم أفهم ردك. يمكنك المساعدة في حجز رحلة طيران."
                
        elif active_form == 'hotel_form':
            if requested_slot == 'ville_hotel':
                message += "🤔 لم أفهم المدينة. في أي مدينة تريد الإقامة؟\n"
                message += "المدن المتاحة: الرباط، الدار البيضاء، مراكش، فاس، أكادير، طنجة"
            elif requested_slot == 'categorie_hotel':
                message += "🤔 لم أفهم فئة الفندق. كم نجمة تريد؟\n"
                message += "الخيارات: 3 نجوم، 4 نجوم، 5 نجوم"
            elif requested_slot == 'nombre_personnes':
                message += "🤔 لم أفهم العدد. كم عدد الأشخاص؟\n"
                message += "مثال: شخصين، 4 أشخاص"
            else:
                message += "🤔 لم أفهم ردك. يمكنني المساعدة في حجز فندق."
                
        else:
            # رسالة عامة عندما لا نكون في form
            message += "🤔 عذراً، لم أتمكن من فهم طلبك بوضوح.\n\n"
            message += "💡 **يمكنني مساعدتك في:**\n"
            message += "   • ✈️ حجز رحلات طيران - قل 'أريد حجز رحلة'\n"
            message += "   • 🏨 حجز فنادق - قل 'أريد حجز فندق'\n"
            message += "   • ❓ الحصول على مساعدة - قل 'مساعدة'\n\n"
            message += "🗣️ **أو اكتب ما تريده بكلمات بسيطة**"
        
        dispatcher.utter_message(text=message)
        return []

class ActionRestart(Action):
    def name(self) -> Text:
        return "action_restart"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        dispatcher.utter_message(
            text="🤖 **وكالة السفر الذكية**\n"
                 "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                 "🔄 تم إعادة تشغيل النظام بنجاح!\n\n"
                 "🌟 مرحباً بك مجدداً في وكالة السفر الذكية!\n\n"
                 "💡 **كيف يمكنني مساعدتك اليوم؟**\n"
                 "   • ✈️ حجز رحلة طيران\n"
                 "   • 🏨 حجز فندق\n"
                 "   • 🎯 تخطيط رحلة"
        )
        
        return [{"event": "restart"}]