import os
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI(title="NaviGo AI Layer")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None
    print("WARNING: GEMINI_API_KEY environment variable not set. Using mock LLM responses.")

class QueryRequest(BaseModel):
    query: str
    lang: str = "en"

# --- Knowledge Base (Lightweight RAG Store) ---
KNOWLEDGE_BASE = {
    "FSSAI": {
        "service_name": "FSSAI Registration",
        "category": "Business",
        "eligibility": ["Handling food manufacturing, processing, or sales.", "Petty food operators need basic registration."],
        "documents": ["Aadhaar", "PAN", "Premises Proof"],
        "process_steps": ["Compile documents.", "Visit foscos.fssai.gov.in.", "Apply for Basic Registration.", "Pay ₹100 fee."],
        "rejection_reasons": ["Blurry electricity bill", "Name mismatch"]
    },
    "PM_KISAN": {
        "service_name": "PM-KISAN Samman Nidhi",
        "category": "Farmer",
        "eligibility": ["Land-holding farmer family.", "Not paying income tax."],
        "documents": ["Aadhaar Card", "Land Ownership (Khatauni)", "Aadhaar-linked Bank Account"],
        "process_steps": ["Visit pmkisan.gov.in", "New Farmer Registration", "Complete e-KYC", "Submit details"],
        "rejection_reasons": ["Aadhaar not linked to bank", "Name mismatch on land record"]
    },
    "NSP": {
        "service_name": "National Scholarship Portal",
        "category": "Student",
        "eligibility": ["Enrolled in recognized institution", "Meets income criteria"],
        "documents": ["Aadhaar", "Marksheet", "Income Certificate"],
        "process_steps": ["Get Income Certificate", "Register on scholarships.gov.in", "Submit application"],
        "rejection_reasons": ["Fake documents", "Missed deadline"]
    },
    "UDYAM": {
        "service_name": "Udyam Registration",
        "category": "Business",
        "eligibility": ["Micro, small or medium enterprise"],
        "documents": ["Aadhaar", "PAN", "Bank Account"],
        "process_steps": ["Visit udyamregistration.gov.in", "Enter Aadhaar", "Provide business details", "Submit"],
        "rejection_reasons": ["Mobile not linked to Aadhaar"]
    }
}

# --- Multi-Agent Functions ---

def agent_intent_discovery(query: str) -> dict:
    if model:
        prompt = f"""
        You are the NaviGo Intent Discovery Agent. Determine the intent and category from the query.
        Valid service IDs: FSSAI, PM_KISAN, NSP, UDYAM.
        Return ONLY valid JSON. Format: {{"intent": "...", "category": "...", "recommended_service_id": "FSSAI"}}
        Query: {query}
        """
        try:
            response = model.generate_content(prompt)
            text = response.text.strip().replace('```json', '').replace('```', '')
            return json.loads(text)
        except Exception as e:
            print(f"LLM Error: {e}")
            
    # Mock Fallback
    q = query.lower()
    if 'farm' in q or 'kisan' in q:
        return {"intent": "Farming Support", "category": "Farmer", "recommended_service_id": "PM_KISAN"}
    elif 'scholarship' in q or 'student' in q:
        return {"intent": "Scholarship", "category": "Student", "recommended_service_id": "NSP"}
    elif 'food' in q or 'restaurant' in q:
        return {"intent": "Start Food Business", "category": "Business", "recommended_service_id": "FSSAI"}
    return {"intent": "Business Registration", "category": "Business", "recommended_service_id": "UDYAM"}

def agent_service_discovery(service_id: str) -> dict:
    return KNOWLEDGE_BASE.get(service_id, KNOWLEDGE_BASE["FSSAI"])

def agent_eligibility(service_data: dict) -> dict:
    # In a full system, this would evaluate user profile against KB rules.
    return {
        "status": "Eligible (Pending exact details)",
        "reasons": ["Matches general criteria based on initial intent."],
        "missing_requirements": []
    }

def agent_document_checklist(service_data: dict) -> dict:
    return {
        "mandatory_documents": service_data["documents"],
        "optional_documents": [],
        "missing_documents": []
    }

def agent_journey_planning(service_data: dict) -> dict:
    return {
        "steps": service_data["process_steps"],
        "estimated_effort": "30-45 mins",
        "next_action": "Gather documents."
    }

# --- Localized Database (Offline Static Fallbacks) ---
LOCALIZED_DATABASE = {
    "hi": {
        "FSSAI Registration": {
            "recommended_service": "FSSAI पंजीकरण और लाइसेंसिंग",
            "eligibility_status": "पात्र (सटीक विवरण लंबित)",
            "required_documents": ["फोटो पहचान प्रमाण (आधार/पैन)", "पासपोर्ट आकार की तस्वीर", "परिसर का प्रमाण (किराया समझौता/बिजली बिल)"],
            "action_plan": ["दस्तावेज़ संकलित करें।", "आधिकारिक FoSCoS पोर्टल (foscos.fssai.gov.in) पर जाएं।", "기본 등록 के लिए आवेदन करें और फॉर्म ए/बी भरें।", "शुल्क (₹100) का भुगतान करें और जमा करें।"],
            "next_step": "दस्तावेज़ एकत्र करें।"
        },
        "PM-KISAN Samman Nidhi": {
            "recommended_service": "पीएम-किसान सम्मान निधि",
            "eligibility_status": "पात्र (सटीक विवरण लंबित)",
            "required_documents": ["आधार कार्ड (अनिवार्य)", "भूमि स्वामित्व दस्तावेज़ (खतौनी)", "आधार-लिंक्ड बैंक खाता"],
            "action_plan": ["आधार और भूमि दस्तावेज़ तैयार रखें।", "pmkisan.gov.in पर जाएं और 'New Farmer Registration' पर क्लिक करें।", "आधार से जुड़े मोबाइल का उपयोग करके ई-केवाईसी पूरा करें।", "भूमि विवरण जमा करें और स्थानीय पटवारी से सत्यापन की प्रतीक्षा करें।"],
            "next_step": "दस्तावेज़ एकत्र करें।"
        },
        "National Scholarship Portal": {
            "recommended_service": "राष्ट्रीय छात्रवृत्ति पोर्टल (NSP)",
            "eligibility_status": "पात्र (सटीक विवरण लंबित)",
            "required_documents": ["आधार कार्ड", "पिछले वर्ष की अंकतालिका", "आय / जाति प्रमाण पत्र"],
            "action_plan": ["आय प्रमाण पत्र प्राप्त करें।", "scholarships.gov.in पर पंजीकरण करें।", "आवेदन पत्र भरें और दस्तावेज़ अपलोड करें।", "सत्यापन के लिए अपने संस्थान में समय सीमा से पहले जमा करें।"],
            "next_step": "दस्तावेज़ एकत्र करें।"
        },
        "Udyam Registration": {
            "recommended_service": "उद्यम (MSME) पंजीकरण",
            "eligibility_status": "पात्र (सटीक विवरण लंबित)",
            "required_documents": ["आधार कार्ड", "पैन कार्ड", "बैंक खाता विवरण"],
            "action_plan": ["आधिकारिक उद्यम पोर्टल (udyamregistration.gov.in) पर जाएं।", "आधार संख्या दर्ज करें और ओटीपी सत्यापित करें।", "व्यवसाय का विवरण भरें और जमा करें।"],
            "next_step": "दस्तावेज़ एकत्र करें।"
        },
        "Document Verification": {
            "recommended_service": "दस्तावेज़ सत्यापन (Document Verification)",
            "eligibility_status": "सार्वभौमिक पात्रता जांच",
            "required_documents": ["सत्यापन के लिए दस्तावेज़"],
            "action_plan": ["अपना दस्तावेज़ अपलोड करें।"],
            "next_step": "दस्तावेज़ अपलोड करें।"
        }
    },
    "kn": {
        "FSSAI Registration": {
            "recommended_service": "FSSAI ನೋಂದಣಿ ಮತ್ತು ಪರವಾನಗಿ",
            "eligibility_status": "ಅರ್ಹರು (ನಿಖರವಾದ ವಿವರಗಳು ಬಾಕಿ ಇವೆ)",
            "required_documents": ["ಫೋಟೋ ಗುರುತಿನ ಪುರಾವೆ (ಆಧಾರ್/ಪ್ಯಾನ್)", "ಪಾಸ್‌ಪೋರ್ಟ್ ಗಾತ್ರದ ಭಾವಚಿತ್ರ", "ಆವರಣದ ಪುರಾವೆ (ಬಾಡಿಗೆ ಒಪ್ಪಂದ/ವಿದ್ಯುತ್ ಬಿಲ್)"],
            "action_plan": ["ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ.", "ಅಧಿಕೃತ FoSCoS ಪೋರ್ಟಲ್‌ಗೆ ಭೇಟಿ ನೀಡಿ (foscos.fssai.gov.in).", "'Apply for License/Registration' ಆಯ್ಕೆಮಾಡಿ.", "ಶುಲ್ಕ ಪಾವತಿಸಿ (₹100) ಮತ್ತು ಸಪ್ಮಿಟ್ ಮಾಡಿ."],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ."
        },
        "PM-KISAN Samman Nidhi": {
            "recommended_service": "ಪಿಎಂ-ಕಿಸಾನ್ ಸಮ್ಮಾನ್ ನಿಧಿ",
            "eligibility_status": "ಅರ್ಹರು (ನಿಖರವಾದ ವಿವರಗಳು ಬಾಕಿ ಇವೆ)",
            "required_documents": ["ಆಧಾರ್ ಕಾರ್ಡ್ (ಕಡ್ಡಾಯ)", "ಭೂ ಮಾಲೀಕತ್ವದ ದಾಖಲೆಗಳು (ಖತೌನಿ)", "ಆಧಾರ್ ಲಿಂಕ್ ಮಾಡಿದ ಸಕ್ರಿಯ ಬ್ಯಾಂಕ್ ಖಾತೆ"],
            "action_plan": ["ಆಧಾರ್ ಮತ್ತು ಭೂ ದಾಖಲೆಗಳನ್ನು ಸಿದ್ಧವಾಗಿಟ್ಟುಕೊಳ್ಳಿ.", "pmkisan.gov.in ಗೆ ಭೇಟಿ ನೀಡಿ ಮತ್ತು 'New Farmer Registration' ಕ್ಲಿಕ್ ಮಾಡಿ.", "ಆಧಾರ್ ಒಟಿಪಿ ಮೂಲಕ ಇ-ಕೆವೈಸಿ ಪೂರ್ಣಗೊಳಿಸಿ.", "ವಿವರಗಳನ್ನು ಸಲ್ಲಿಸಿ ಮತ್ತು ಪರಿಶೀಲನೆಗಾಗಿ ಕಾಯಿರಿ."],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ."
        },
        "National Scholarship Portal": {
            "recommended_service": "ರಾಷ್ಟ್ರೀಯ ವಿದ್ಯಾರ್ಥಿವೇತನ ಪೋರ್ಟಲ್ (NSP)",
            "eligibility_status": "ಅರ್ಹರು (ನಿಖರವಾದ ವಿವರಗಳು ಬಾಕಿ ಇವೆ)",
            "required_documents": ["ಆಧಾರ್ ಕಾರ್ಡ್", "ಹಿಂದಿನ ವರ್ಷದ ಅಂಕಪಟ್ಟಿ", "ಆದಾಯ / ಜಾತಿ ಪ್ರಮಾಣಪತ್ರ"],
            "action_plan": ["ಆದಾಯ ಪ್ರಮಾಣಪತ್ರವನ್ನು ಪಡೆಯಿರಿ.", "scholarships.gov.in ನಲ್ಲಿ ನೋಂದಾಯಿಸಿ.", "ಅರ್ಜಿಯನ್ನು ಸಲ್ಲಿಸಿ ಮತ್ತು ದಾಖಲೆಗಳನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.", "ಪರಿಶೀಲನೆಗಾಗಿ ಸಂಸ್ಥೆಗೆ ಸಲ್ಲಿಸಿ."],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ."
        },
        "Udyam Registration": {
            "recommended_service": "MSME ಉದ್ಯಮ ನೋಂದಣಿ",
            "eligibility_status": "ಅರ್ಹರು (ನಿಖರವಾದ ವಿವರಗಳು ಬಾಕಿ ಇವೆ)",
            "required_documents": ["ಆಧಾರ್ ಕಾರ್ಡ್", "ಪ್ಯಾನ್ ಕಾರ್ಡ್", "ಬ್ಯಾಂಕ್ ಖಾತೆ ವಿವರಗಳು"],
            "action_plan": ["udyamregistration.gov.in ಗೆ ಭೇಟಿ ನೀಡಿ.", "ಆಧಾರ್ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ ಮತ್ತು ಒಟಿಪಿ ಪರಿಶೀಲಿಸಿ.", "ವಿವರಗಳನ್ನು ಭರ್ತಿ ಮಾಡಿ ಮತ್ತು ಸಲ್ಲಿಸಿ."],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ."
        },
        "Document Verification": {
            "recommended_service": "ದಾಖಲೆ ಪರಿಶೀಲನೆ (Document Verification)",
            "eligibility_status": "ಸಾರ್ವತ್ರಿಕ ಅರ್ಹತಾ ಪರಿಶೀಲನೆ",
            "required_documents": ["ಪರಿಶೀಲನೆಗಾಗಿ ದಾಖಲೆ"],
            "action_plan": ["ನಿಮ್ಮ ದಾಖಲೆಯನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ."],
            "next_step": "ದಾಖಲೆ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ."
        }
    },
    "te": {
        "FSSAI Registration": {
            "recommended_service": "FSSAI రిజిస్ట్రేషన్ & లైసెన్సింగ్",
            "eligibility_status": "అర్హులు (ఖచ్చితమైన వివరాలు పెండింగ్‌లో ఉన్నాయి)",
            "required_documents": ["ఫోటో గుర్తింపు రుజువు (ఆధార్/పాన్)", "పాసపోర్ట్ సైజు ఫోటో", "ఆవరణల రుజువు (అద్దె ఒప్పందం/కరెంటు బిల్లు)"],
            "action_plan": ["పత్రాలను సేకరించండి.", "అధికారిక FoSCoS పోర్టల్ (foscos.fssai.gov.in) సందర్శించండి.", "దరఖాస్తు చేసుకోండి.", "ఫీజు (₹100) చెల్లించి సమర్పించండి."],
            "next_step": "పత్రాలను సేకరించండి."
        },
        "PM-KISAN Samman Nidhi": {
            "recommended_service": "పీఎం-కిసాన్ సమ్మాన్ నిధి",
            "eligibility_status": "అర్హులు (ఖచ్చితమైన వివరాలు పెండింగ్‌లో ఉన్నాయి)",
            "required_documents": ["ఆధార్ కార్డ్ (తప్పనిసరి)", "భూమి యాజమాన్య పత్రాలు (ఖతౌనీ)", "ఆధార్ లింక్డ్ బ్యాంక్ ఖాతా"],
            "action_plan": ["ఆధార్ మరియు భూమి పత్రాలను సిద్ధంగా ఉంచుకోండి.", "pmkisan.gov.in సందర్శించి 'New Farmer Registration' క్లిక్ చేయండి.", "ఈ-కేవైసీ పూర్తి చేయండి.", "భూమి వివరాలను సమర్పించి ధృవీకరణ కోసం వేచి ఉండండి."],
            "next_step": "పత్రాలను సేకరించండి."
        },
        "National Scholarship Portal": {
            "recommended_service": "నేషనల్ స్కాలర్‌షిప్ పోర్టల్ (NSP)",
            "eligibility_status": "అర్హులు (ఖచ్చితమైన వివరాలు పెండింగ్‌లో ఉన్నాయి)",
            "required_documents": ["ఆధಾರ್ కార్డ్", "క్రితం సంవత్సరం మార్కుల జాబితా", "ఆదాయం / కుల ధృవీకరణ పత్రం"],
            "action_plan": ["ఆదాయ ధృవీకరణ పత్రం పొందండి.", "scholarships.gov.in లో నమోదు చేసుకోండి.", "దరఖాస్తును సమర్పించి పత్రాలను అప్‌లోడ్ చేయండి.", "ధృవీకరణ కోసం మీ విద్యా సంస్థకు సమర్పించండి."],
            "next_step": "పత్రాలను సేకరించండి."
        },
        "Udyam Registration": {
            "recommended_service": "MSME ఉద్యమ రిజిస్ట్రేషన్",
            "eligibility_status": "అర్హులు (ఖచ్చితమైన వివరాలు పెండింగ్‌లో ఉన్నాయి)",
            "required_documents": ["ఆధార్ కార్డ్", "పాన్ కార్డ్", "బ్యాంక్ ఖాతా వివరాలు"],
            "action_plan": ["udyamregistration.gov.in సందర్శించండి.", "ఆధార్ నంబర్ నమోదు చేసి ఓటీపీ ధృవీకరించండి.", "వ్యాపార వివరాలు సమర్పించండి."],
            "next_step": "పత్రాలను సేకరించండి."
        },
        "Document Verification": {
            "recommended_service": "పత్రాల ధృవీకరణ (Document Verification)",
            "eligibility_status": "సార్వత్రిక అర్హత తనిఖీ",
            "required_documents": ["ధృవీకరణ కోసం పత్రం"],
            "action_plan": ["మీ పత్రాన్ని అప్‌లోడ్ చేయండి."],
            "next_step": "పత్రాన్ని అప్‌లోడ్ చేయండి."
        }
    }
}

LOCALIZED_DOC_ANALYSIS = {
    "hi": {
        "summary": "अपलोड की गई फ़ाइल का विश्लेषण किया गया",
        "detected_issues": ["पता प्रमाण धुंधला है।", "सुनिश्चित करें कि यह आवेदन नाम से बिल्कुल मेल खाता है।"],
        "recommendations": ["दस्तावेज़ की एक नई, स्पष्ट तस्वीर लें।", "पोर्टल पर फिर से अपलोड करें।"]
    },
    "kn": {
        "summary": "ಅಪ್‌ಲೋಡ್ ಮಾಡಿದ ಫೈಲ್ ಅನ್ನು ವಿಶ್ಲೇಷಿಸಲಾಗಿದೆ",
        "detected_issues": ["ವಿಳಾಸದ ಪುರಾವೆ ಅಸ್ಪಷ್ಟವಾಗಿದೆ.", "ಇದು ಅರ್ಜಿಯ ಹೆಸರಿಗೆ ನಿಖರವಾಗಿ ಹೊಂದಿಕೆಯಾಗುತ್ತದೆಯೇ ಎಂದು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ."],
        "recommendations": ["ದಾಖಲೆಯ ಹೊಸ, ಸ್ಪಷ್ಟ ಚಿತ್ರವನ್ನು ತೆಗೆದುಕೊಳ್ಳಿ.", "ಪೋರ್ಟಲ್‌ಗೆ ಮರು-ಅಪ್‌ಲೋಡ್ ಮಾಡಿ."]
    },
    "te": {
        "summary": "అప్‌లోడ్ చేసిన ఫైల్ విశ్లేషించబడింది",
        "detected_issues": ["చిరునామా రుజువు అస్పష్టంగా ఉంది.", "ఇది దరఖాస్తు పేరుతో సరిగ్గా సరిపోలుతోందని నిర్ధారించుకోండి."],
        "recommendations": ["పత్రం యొక్క కొత్త, స్పష్టమైన ఫోటో తీసుకోండి.", "పోర్టల్‌లో మళ్లీ అప్‌లోడ్ చేయండి."]
    }
}

# --- AI Translation Helper ---
def translate_payload(payload: dict, target_lang: str) -> dict:
    if target_lang == "en":
        return payload
    
    # 1. Check if we have static offline translations for this service
    service_name = payload.get("recommended_service")
    if target_lang in LOCALIZED_DATABASE and service_name in LOCALIZED_DATABASE[target_lang]:
        return LOCALIZED_DATABASE[target_lang][service_name]
    
    # 2. Check if we have static offline translations for document analysis
    if "detected_issues" in payload:
        if target_lang in LOCALIZED_DOC_ANALYSIS:
            localized = LOCALIZED_DOC_ANALYSIS[target_lang].copy()
            if "summary" in payload and "filename" in payload.get("summary", ""):
                filename = payload["summary"].split(": ")[-1]
                localized["summary"] = f"{localized['summary']}: {filename}"
            return localized

    # 3. Dynamic online translation fallback via Gemini
    if not model:
        return payload
    
    lang_names = {"hi": "Hindi", "kn": "Kannada", "te": "Telugu"}
    target_lang_name = lang_names.get(target_lang, "English")
    
    prompt = f"""
    You are a professional translation assistant. Translate the values of the following JSON object to {target_lang_name}.
    Keep the structure, keys, list lengths, and URLs/acronyms (like FSSAI, PAN, Aadhaar, pmkisan.gov.in, foscos.fssai.gov.in) exactly unchanged.
    Only translate descriptions, lists of steps, and text strings.
    
    JSON to translate:
    {json.dumps(payload)}
    
    Return ONLY valid raw JSON without code blocks.
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        if text.startswith("{") or text.startswith("["):
            return json.loads(text)
        else:
            lines = text.split('\n')
            clean_lines = [l for l in lines if not l.strip().startswith('```')]
            return json.loads('\n'.join(clean_lines))
    except Exception as e:
        print(f"Translation Error: {e}")
        return payload

# --- API Routes ---

@app.post("/api/chat")
def chat_endpoint(request: QueryRequest):
    # Agent 1: Intent Discovery
    intent_data = agent_intent_discovery(request.query)
    
    # Agent 2: Service Retrieval (RAG Mock)
    service_data = agent_service_discovery(intent_data["recommended_service_id"])
    
    # Agent 3: Eligibility
    eligibility = agent_eligibility(service_data)
    
    # Agent 4: Documents
    docs = agent_document_checklist(service_data)
    
    # Agent 5: Journey
    journey = agent_journey_planning(service_data)

    payload = {
        "recommended_service": service_data["service_name"],
        "eligibility_status": eligibility["status"],
        "required_documents": docs["mandatory_documents"],
        "action_plan": journey["steps"],
        "next_step": journey["next_action"]
    }
    
    if request.lang != "en":
        payload = translate_payload(payload, request.lang)
        
    return payload

@app.post("/api/analyze_document")
def analyze_document(file: UploadFile = File(...), lang: str = "en"):
    # Agent 6: Document Understanding
    # In production, pass file.file to Gemini Vision
    payload = {
        "summary": f"Analyzed uploaded file: {file.filename}",
        "detected_issues": ["The address proof is blurry.", "Ensure it matches the application name exactly."],
        "recommendations": [
            "Take a new, clear photograph of the document.",
            "Re-upload to the portal."
        ]
    }
    if lang != "en":
        payload = translate_payload(payload, lang)
    return payload

if __name__ == "__main__":
    import uvicorn
    print("Starting NaviGo AI Layer Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
