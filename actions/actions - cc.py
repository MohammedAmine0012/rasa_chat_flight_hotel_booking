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
            dispatcher.utter_message(text="متى تريد السفر؟ مثال: 15 مايو، غداً، الأسبوع القادم")
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
            if any(moroccan_city in entity_value for moroccan_city in MOROCCAN_CITIES):
                city = entity_value
                logger.info(f"Found hotel city in entity: {city}")
                break
                
        if not city and slot_value:
            city = slot_value
            
        if city and any(moroccan_city in city for moroccan_city in MOROCCAN_CITIES):
            logger.info(f"Valid hotel city detected: {city}")
            return {"ville_hotel": city}
        else:
            dispatcher.utter_message(
                text="عذراً، يرجى اختيار مدينة صحيحة للإقامة.\n"
                     "المدن المتاحة: الرباط، الدار البيضاء، مراكش، فاس، أكادير، طنجة"
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
            if "3" in slot_value_clean or "ثلاث" in slot_value_clean:
                logger.info("Selected 3-star hotel")
                return {"categorie_hotel": "3 نجوم"}
            elif "4" in slot_value_clean or "أربع" in slot_value_clean:
                logger.info("Selected 4-star hotel")
                return {"categorie_hotel": "4 نجوم"}
            elif "5" in slot_value_clean or "خمس" in slot_value_clean:
                logger.info("Selected 5-star hotel")
                return {"categorie_hotel": "5 نجوم"}
            elif "فاخر" in slot_value_clean or "luxury" in slot_value_clean.lower():
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
                'economique': 0,
                'affaires': 1,
                'premiere': 2
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
            return [SlotSet("flight_details", flight_details)]
            
        except Exception as e:
            logger.error(f"Error in ActionSearchFlights: {str(e)}")
            dispatcher.utter_message(text="عذراً، حدث خطأ أثناء البحث عن الرحلات. يرجى المحاولة مرة أخرى.")
            return []

class ActionSearchHotels(Action):
    def name(self) -> Text:
        return "action_search_hotels"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        ville_hotel = tracker.get_slot("ville_hotel")
        categorie_hotel = tracker.get_slot("categorie_hotel") 
        nombre_personnes = tracker.get_slot("nombre_personnes")
        quartier = tracker.get_slot("quartier")
        
        logger.info(f"Hotel search: {ville_hotel}, {categorie_hotel}, {nombre_personnes} persons")
        
        # التأكد من وجود المعلومات الأساسية
        if not ville_hotel:
            dispatcher.utter_message(text="أحتاج إلى معرفة المدينة أولاً. في أي مدينة تريد الإقامة؟")
            return []
            
        if not categorie_hotel:
            dispatcher.utter_message(text="أحتاج إلى معرفة فئة الفندق. كم نجمة تريد؟ (3، 4، 5 نجوم)")
            return []
            
        if not nombre_personnes:
            dispatcher.utter_message(text="أحتاج إلى معرفة عدد الأشخاص. كم شخص؟")
            return []
        
        # إنشاء رسالة البحث
        message = f"🏨 تم العثور على فنادق مميزة في {ville_hotel}\n"
        message += f"⭐ الفئة: {categorie_hotel}\n"
        message += f"👥 عدد الأشخاص: {nombre_personnes}\n"
        
        if quartier:
            message += f"📍 المنطقة المفضلة: {quartier}\n"
            
        message += "\n" + "="*40 + "\n\n"
        
        # عرض الخيارات بناءً على المدينة والفئة
        if "مراكش" in ville_hotel:
            message += "🏨 **الخيار الأول: فندق المامونية الشهير**\n"
            message += "   💰 السعر: 1,200 درهم/ليلة\n"
            message += "   ⭐ التقييم: 4.8/5\n"
            message += "   🎯 المميزات: سبا فاخر، 3 مطاعم، حدائق تاريخية\n"
            message += "   📍 الموقع: وسط المدينة القديمة\n\n"
            
            message += "🏨 **الخيار الثاني: فندق أطلس مراكش**\n"
            message += "   💰 السعر: 850 درهم/ليلة\n"
            message += "   ⭐ التقييم: 4.5/5\n"
            message += "   🎯 المميزات: مسبح، إفطار مجاني، واي فاي\n"
            message += "   📍 الموقع: المدينة الجديدة\n\n"
            
        elif "الرباط" in ville_hotel:
            message += "🏨 **الخيار الأول: فندق تور حسان**\n"
            message += "   💰 السعر: 900 درهم/ليلة\n"
            message += "   ⭐ التقييم: 4.6/5\n"
            message += "   🎯 المميزات: إطلالة على البحر، مطعم راقي\n"
            message += "   📍 الموقع: قرب صومعة حسان\n\n"
            
            message += "🏨 **الخيار الثاني: فندق هيلتون الرباط**\n"
            message += "   💰 السعر: 1,100 درهم/ليلة\n"
            message += "   ⭐ التقييم: 4.7/5\n"
            message += "   🎯 المميزات: مركز أعمال، نادي رياضي\n"
            message += "   📍 الموقع: وسط المدينة\n\n"
            
        else:
            # فنادق عامة للمدن الأخرى
            message += "🏨 **الخيار الأول: فندق الأطلس الكبير**\n"
            message += "   💰 السعر: 800 درهم/ليلة\n"
            message += "   ⭐ التقييم: 4.5/5\n"
            message += "   🎯 المميزات: مسبح، إفطار مجاني، واي فاي\n"
            message += "   📍 الموقع: وسط المدينة\n\n"
            
            message += "🏨 **الخيار الثاني: فندق النخيل الذهبي**\n"
            message += "   💰 السعر: 650 درهم/ليلة\n"
            message += "   ⭐ التقييم: 4.2/5\n"
            message += "   🎯 المميزات: موقع ممتاز، خدمة 24/7\n"
            message += "   📍 الموقع: قرب المعالم السياحية\n\n"
        
        message += "🔹 أي فندق تفضل؟ قل **'الخيار الأول'** أو **'الخيار الثاني'**"
        
        dispatcher.utter_message(text=message)
        return []

class ActionSelectOption(Action):
    def name(self) -> Text:
        return "action_select_option"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the user's message
        user_message = tracker.latest_message.get('text', '').lower()
        
        # Extract the option number
        option_number = None
        if 'الخيار رقم' in user_message:
            try:
                option_number = int(user_message.split('الخيار رقم')[1].strip())
            except:
                pass
        elif 'الخيار الأول' in user_message or 'الخيار 1' in user_message:
            option_number = 1
        elif 'الخيار الثاني' in user_message or 'الخيار 2' in user_message:
            option_number = 2
        elif 'الخيار الثالث' in user_message or 'الخيار 3' in user_message:
            option_number = 3
        elif 'الخيار الرابع' in user_message or 'الخيار 4' in user_message:
            option_number = 4
        elif 'الخيار الخامس' in user_message or 'الخيار 5' in user_message:
            option_number = 5

        if not option_number or option_number < 1 or option_number > 5:
            dispatcher.utter_message(
                text="لم أتمكن من فهم اختيارك بوضوح.\n"
                     "يرجى قول 'الخيار رقم X' حيث X هو رقم الرحلة (من 1 إلى 5)"
            )
            return []

        # Get flight details from the tracker
        flight_details = tracker.get_slot("flight_details")
        if not flight_details:
            dispatcher.utter_message(
                text="عذراً، لم يتم العثور على تفاصيل الرحلات. يرجى البحث عن الرحلات أولاً."
            )
            return []

        try:
            if isinstance(flight_details, str):
                import json
                flight_details = json.loads(flight_details)
            elif not isinstance(flight_details, list):
                flight_details = []
            if option_number > len(flight_details):
                dispatcher.utter_message(
                    text=f"عذراً، الرقم {option_number} غير متوفر. يرجى اختيار رقم من 1 إلى {len(flight_details)}"
                )
                return []

            selected_flight = flight_details[option_number - 1]
            
            # Confirm the selection
            message = f"✅ ممتاز! لقد اخترت **الخيار رقم {option_number}**\n\n"
            message += f"🛫 {selected_flight['airline']}\n"
            message += f"📅 تاريخ المغادرة: {selected_flight['departure_time']}\n"
            message += f"📅 تاريخ العودة: {selected_flight['arrival_time']}\n"
            message += f"⏱️ مدة الرحلة: {selected_flight['duration']}\n"
            message += f"🛑 عدد التوقفات: {selected_flight['stops']}\n"
            message += f"💰 السعر: {selected_flight['price_mad']}\n\n"
            message += "🤝 هل تريد المتابعة مع هذا الاختيار؟\n"
            message += "• قل **'نعم'** أو **'أؤكد'** للمتابعة\n"
            message += "• قل **'لا'** أو **'غير'** للتغيير"
            
            dispatcher.utter_message(text=message)
            
            # Save the selected option
            return [{"event": "slot", "name": "selected_option", "value": str(option_number)}]
            
        except Exception as e:
            logger.error(f"Error processing flight selection: {str(e)}")
            dispatcher.utter_message(
                text="عذراً، حدث خطأ أثناء معالجة اختيارك. يرجى المحاولة مرة أخرى."
            )
            return []

class ActionConfirmReservation(Action):
    def name(self) -> Text:
        return "action_confirm_reservation"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # التحقق من وجود خيار محدد
        selected_option = tracker.get_slot("selected_option")
        
        if not selected_option:
            dispatcher.utter_message(
                text="🤖 **وكالة السفر الذكية**\n"
                     "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                     "يبدو أنك تريد التأكيد، لكن لم تختر خياراً بعد.\n"
                     "دعني أكمل مساعدتك في الحجز أولاً!"
            )
            return []
        
        # تحديد نوع الحجز
        is_flight_booking = bool(tracker.get_slot("ville_depart") or tracker.get_slot("ville_destination"))
        is_hotel_booking = bool(tracker.get_slot("ville_hotel"))
        
        # جمع تفاصيل الحجز
        ville_depart = tracker.get_slot("ville_depart")
        ville_destination = tracker.get_slot("ville_destination")
        date_depart = tracker.get_slot("date_depart")
        classe = tracker.get_slot("classe")
        ville_hotel = tracker.get_slot("ville_hotel")
        categorie_hotel = tracker.get_slot("categorie_hotel")
        nombre_personnes = tracker.get_slot("nombre_personnes")
        
        logger.info(f"Confirming reservation - Option: {selected_option}, Flight: {is_flight_booking}, Hotel: {is_hotel_booking}")
        
        # Build confirmation message with HTML structure for card display
        message = (
            "<booking-confirmation>"
            "<div class='booking-header'>🤖 <b>وكالة السفر الذكية</b></div>"
            "<div class='booking-section'>"
            "<b>🎉 تأكيد الحجز</b><br>"
            "✈️ <b>تفاصيل الرحلة</b><br>"
            f"📍 <b>المغادرة:</b> {ville_depart if ville_depart else '-'}<br>"
            f"📍 <b>الوجهة:</b> {ville_destination if ville_destination else '-'}<br>"
            f"📅 <b>تاريخ السفر:</b> {date_depart if date_depart else '-'}<br>"
            f"💺 <b>الدرجة:</b> {classe if classe else '-'}<br>"
            "</div>"
            "<div class='booking-section'>"
            "<b>📋 معلومات إضافية</b><br>"
            "📧 <b>تأكيد الحجز:</b> سيتم إرسال تفاصيل الحجز عبر البريد الإلكتروني خلال 10 دقائق<br>"
            "احتفظ برقم الحجز للمراجعة"
            "</div>"
            "<div class='booking-section'>"
            "<b>📱 خدمة العملاء:</b><br>"
            "📞 الهاتف: +212-5XX-XXXXXX<br>"
            "💬 واتساب: +212-6XX-XXXXXX<br>"
            "⏰ متاح 24/7"
            "</div>"
            "<div class='booking-section'>"
            "<b>🎯 نصائح مهمة:</b><br>"
            "تأكد من صحة جواز السفر (للطيران الدولي)<br>"
            "اوصل للمطار قبل 3 ساعات (دولي) أو 2 ساعة (محلي)<br>"
            "تحقق من شروط الإلغاء والتعديل"
            "</div>"
            "<div class='booking-section'>"
            "<b>🔄 لحجز جديد:</b> قل 'مرحبا' أو اضغط إعادة التشغيل"
            "</div>"
            "<div class='booking-footer'>"
            "🌟 <b>شكراً لثقتك بوكالة السفر الذكية!</b> ✈️🏨 نتمنى لك رحلة سعيدة وإقامة ممتعة! ✨"
            "</div>"
            "</booking-confirmation>"
        )
        
        dispatcher.utter_message(text=message)
        
        # مسح البيانات بعد التأكيد للاستعداد لحجز جديد
        return [
            {"event": "slot", "name": "selected_option", "value": None},
            {"event": "slot", "name": "ville_depart", "value": None},
            {"event": "slot", "name": "ville_destination", "value": None},
            {"event": "slot", "name": "date_depart", "value": None},
            {"event": "slot", "name": "classe", "value": None},
            {"event": "slot", "name": "ville_hotel", "value": None},
            {"event": "slot", "name": "categorie_hotel", "value": None},
            {"event": "slot", "name": "nombre_personnes", "value": None}
        ]

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