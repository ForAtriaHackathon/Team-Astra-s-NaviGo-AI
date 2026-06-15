import os
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
        "description": "Official registration for all food-related businesses in India.",
        "eligibility": [
            "Any person handling food manufacturing, processing, or sales.",
            "Petty food business operators (turnover below ₹12 Lakhs) need Basic Registration.",
            "Turnover above ₹12 Lakhs requires a State or Central License."
        ],
        "documents": [
            "Photo ID Proof: Aadhaar / PAN / Voter ID. Must be clearly visible.",
            "Passport Size Photograph: Recent color photo.",
            "Proof of Premises: Rent agreement, Electricity bill, or NOC from owner."
        ],
        "process_steps": [
            "Compile your ID, Photo, and Premise proof.",
            "Visit the official FoSCoS portal (foscos.fssai.gov.in).",
            "Select 'Apply for License/Registration' and fill Form A/B.",
            "Pay the fee (₹100 for Basic Registration) and submit."
        ],
        "rejection_reasons": ["Blurry electricity bill", "Name mismatch"]
    },
    "PM_KISAN": {
        "service_name": "PM-KISAN Samman Nidhi",
        "category": "Farmer",
        "description": "Income support of ₹6,000 per year to all land-holding farmer families.",
        "eligibility": [
            "Must be a land-holding farmer family.",
            "Cultivable land must be registered in your name.",
            "Must not be an institutional landholder, current/former minister, or paying income tax."
        ],
        "documents": [
            "Aadhaar Card: Mandatory for e-KYC.",
            "Land Ownership Documents: Khatauni / Patta.",
            "Bank Account Details: Aadhaar-seeded active bank account."
        ],
        "process_steps": [
            "Keep your Aadhaar and Land documents ready.",
            "Visit pmkisan.gov.in and click on 'New Farmer Registration'.",
            "Complete OTP-based e-KYC using your Aadhaar linked mobile.",
            "Submit land details and await verification from local Patwari."
        ],
        "rejection_reasons": ["Aadhaar not linked to bank", "Name mismatch on land record"]
    },
    "NSP": {
        "service_name": "National Scholarship Portal",
        "category": "Student",
        "description": "One-stop platform for all government scholarships for students.",
        "eligibility": [
            "Must be a citizen of India.",
            "Must be enrolled in a recognized educational institution.",
            "Income and academic merit thresholds vary by specific scheme."
        ],
        "documents": [
            "Aadhaar Card: Linked to mobile and bank.",
            "Previous Year Marksheet: Proof of academic progression.",
            "Income / Caste Certificate: Issued by competent authority (if applicable)."
        ],
        "process_steps": [
            "Register on scholarships.gov.in using your Aadhaar.",
            "Log in and fill the common application form.",
            "Upload scanned copies of required documents.",
            "Submit before the deadline to your institute for verification."
        ],
        "rejection_reasons": ["Fake documents", "Missed deadline"]
    },
    "UDYAM": {
        "service_name": "Udyam Registration",
        "category": "Business",
        "description": "Zero-cost government registration for Micro, Small, and Medium Enterprises.",
        "eligibility": [
            "Any individual intending to establish a micro, small or medium enterprise.",
            "Based entirely on self-declaration of investment and turnover."
        ],
        "documents": [
            "Aadhaar Card: Must be linked to mobile number for OTP validation.",
            "PAN Card: Business or Individual PAN.",
            "Bank Account Details: Account number and IFSC code."
        ],
        "process_steps": [
            "Visit udyamregistration.gov.in (Official free portal).",
            "Enter Aadhaar number and verify via OTP.",
            "Fill in PAN details to auto-fetch tax data.",
            "Provide business address and activity details, then submit."
        ],
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
            "description": "भारत में सभी खाद्य-संबंधित व्यवसायों के लिए आधिकारिक पंजीकरण।",
            "eligibility_status": "पात्रता की पुष्टि की गई",
            "eligibility_criteria": [
                "खाद्य निर्माण, प्रसंस्करण या बिक्री संभालने वाला कोई भी व्यक्ति।",
                "छोटे खाद्य व्यवसाय संचालक (₹12 लाख से कम कारोबार) को मूल पंजीकरण की आवश्यकता है।",
                "₹12 लाख से अधिक के कारोबार के लिए राज्य या केंद्रीय लाइसेंस की आवश्यकता होती है।"
            ],
            "required_documents": [
                "फोटो पहचान प्रमाण: आधार / पैन / वोटर आईडी। स्पष्ट रूप से दिखाई देना चाहिए।",
                "पासपोर्ट आकार की तस्वीर: हालिया रंगीन फोटो।",
                "परिसर का प्रमाण: किराया समझौता, बिजली बिल, या मालिक से एनओसी।"
            ],
            "action_plan": [
                "अपनी आईडी, फोटो और परिसर का प्रमाण संकलित करें।",
                "आधिकारिक FoSCoS पोर्टल (foscos.fssai.gov.in) पर जाएं।",
                "'Apply for License/Registration' चुनें और फॉर्म ए/बी भरें।",
                "शुल्क (मूल पंजीकरण के लिए ₹100) का भुगतान करें और जमा करें।"
            ],
            "next_step": "दस्तावेज़ संकलित करें और आवेदन शुरू करें।"
        },
        "PM-KISAN Samman Nidhi": {
            "recommended_service": "पीएम-किसान सम्मान निधि",
            "description": "सभी भूमिधारक किसान परिवारों को प्रति वर्ष ₹6,000 की आय सहायता।",
            "eligibility_status": "पात्रता की पुष्टि की गई",
            "eligibility_criteria": [
                "एक भूमिधारक किसान परिवार होना चाहिए।",
                "खेती योग्य भूमि आपके नाम पर पंजीकृत होनी चाहिए।",
                "संस्थागत भूमिधारक, वर्तमान/पूर्व मंत्री, या आयकर दाता नहीं होना चाहिए।"
            ],
            "required_documents": [
                "आधार कार्ड: ई-केवाईसी के लिए अनिवार्य।",
                "भूमि स्वामित्व दस्तावेज़: खतौनी / पट्टा।",
                "बैंक खाता विवरण: आधार-सीडेड सक्रिय बैंक खाता।"
            ],
            "action_plan": [
                "अपने आधार और भूमि दस्तावेज़ तैयार रखें।",
                "pmkisan.gov.in पर जाएं और 'New Farmer Registration' पर क्लिक करें।",
                "आधार से जुड़े मोबाइल का उपयोग करके ओटीपी-आधारित ई-केवाईसी पूरा करें।",
                "भूमि विवरण जमा करें और स्थानीय पटवारी से सत्यापन की प्रतीक्षा करें।"
            ],
            "next_step": "दस्तावेज़ संकलित करें और ई-केवाईसी शुरू करें।"
        },
        "National Scholarship Portal": {
            "recommended_service": "राष्ट्रीय छात्रवृत्ति पोर्टल (NSP)",
            "description": "छात्रों के लिए सभी सरकारी छात्रवृत्तियों के लिए वन-स्टॉप प्लेटफॉर्म।",
            "eligibility_status": "पात्रता की पुष्टि की गई",
            "eligibility_criteria": [
                "भारत का नागरिक होना चाहिए।",
                "एक मान्यता प्राप्त शैक्षणिक संस्थान में नामांकित होना चाहिए।",
                "विशिष्ट योजना के अनुसार आय और शैक्षणिक योग्यता की सीमाएं लागू होती हैं।"
            ],
            "required_documents": [
                "आधार कार्ड: मोबाइल और बैंक से जुड़ा हुआ।",
                "पिछले वर्ष की अंकतालिका: शैक्षणिक प्रगति का प्रमाण।",
                "आय / जाति प्रमाण पत्र: सक्षम प्राधिकारी द्वारा जारी (यदि लागू हो)।"
            ],
            "action_plan": [
                "अपने आधार का उपयोग करके scholarships.gov.in पर पंजीकरण करें।",
                "लॉग इन करें और सामान्य आवेदन पत्र भरें।",
                "आवश्यक दस्तावेजों की स्कैन की गई प्रतियां अपलोड करें।",
                "सत्यापन के लिए समय सीमा से पहले अपने संस्थान में जमा करें।"
            ],
            "next_step": "दस्तावेज़ संकलित करें और छात्रवृत्ति पंजीकरण शुरू करें।"
        },
        "Udyam Registration": {
            "recommended_service": "उद्यम (MSME) पंजीकरण",
            "description": "सूक्ष्म, लघु और मध्यम उद्यमों के लिए शून्य-लागत सरकारी पंजीकरण।",
            "eligibility_status": "पात्रता की पुष्टि की गई",
            "eligibility_criteria": [
                "सूक्ष्म, लघु या मध्यम उद्यम स्थापित करने का इरादा रखने वाला कोई भी व्यक्ति।",
                "पूरी तरह से निवेश और कारोबार की स्व-घोषणा पर आधारित।"
            ],
            "required_documents": [
                "आधार कार्ड: ओटीपी सत्यापन के लिए मोबाइल नंबर से लिंक होना चाहिए।",
                "पैन कार्ड: व्यवसाय या व्यक्तिगत पैन।",
                "बैंक खाता विवरण: खाता संख्या और आईएफएससी कोड।"
            ],
            "action_plan": [
                "उद्यम पंजीकरण की आधिकारिक मुफ्त वेबसाइट (udyamregistration.gov.in) पर जाएं।",
                "आधार संख्या दर्ज करें और ओटीपी सत्यापित करें।",
                "कर डेटा को ऑटो-फ़ेच करने के लिए पैन विवरण दर्ज करें।",
                "व्यवसाय का पता और गतिविधि का विवरण प्रदान करें, फिर जमा करें।"
            ],
            "next_step": "दस्तावेज़ संकलित करें और उद्यम पंजीकरण शुरू करें।"
        },
        "Document Verification": {
            "recommended_service": "दस्तावेज़ सत्यापन (Document Verification)",
            "description": "अस्वीकृति पत्रों या विसंगतियों के लिए एआई-संचालित दस्तावेज़ विश्लेषण।",
            "eligibility_status": "सार्वभौमिक पात्रता जांच",
            "eligibility_criteria": [
                "कोई भी दस्तावेज, रसीद, या सरकारी पत्र जिसका विश्लेषण किया जाना है。"
            ],
            "required_documents": [
                "सत्यापन के लिए दस्तावेज़: पीडीएफ, पीएनजी, या जेपीजी प्रारूप।"
            ],
            "action_plan": [
                "अपना दस्तावेज़ अपलोड करें।",
                "सत्यापन रिपोर्ट प्राप्त करें और सुधारात्मक कदमों का पालन करें。"
            ],
            "next_step": "विश्लेषण के लिए दस्तावेज़ अपलोड करें。"
        }
    },
    "kn": {
        "FSSAI Registration": {
            "recommended_service": "FSSAI ನೋಂದಣಿ ಮತ್ತು ಪರವಾನಗಿ",
            "description": "ಭಾರತದಲ್ಲಿನ ಎಲ್ಲಾ ಆಹಾರ-ಸಂಬಂಧಿತ ವ್ಯವಹಾರಗಳಿಗೆ ಅಧಿಕೃತ ನೋಂದಣಿ.",
            "eligibility_status": "ಅರ್ಹತೆ ದೃಢೀಕರಿಸಲ್ಪಟ್ಟಿದೆ",
            "eligibility_criteria": [
                "ಆಹಾರ್ ತಯಾರಿಕೆ, ಸಂಸ್ಕರಣೆ ಅಥವಾ ಮಾರಾಟವನ್ನು ನಿರ್ವಹಿಸುವ ಯಾವುದೇ ವ್ಯಕ್ತಿ.",
                "ಸಣ್ಣ ಆಹಾರ ವ್ಯವಹಾರ ಆಪರೇಟರ್‌ಗಳಿಗೆ (₹12 ಲಕ್ಷಕ್ಕಿಂತ ಕಡಿಮೆ ವಹಿವಾಟು) ಮೂಲ ನೋಂದಣಿ ಅಗತ್ಯವಿದೆ.",
                "₹12 ಲಕ್ಷಕ್ಕಿಂತ ಹೆಚ್ಚಿನ ವಹಿವಾಟಿಗೆ ರಾಜ್ಯ ಅಥವಾ ಕೇಂದ್ರ ಪರವಾನಗಿ ಅಗತ್ಯವಿರುತ್ತದೆ."
            ],
            "required_documents": [
                "ಫೋಟೋ ಐಡಿ ಪುರಾವೆ: ಆಧಾರ್ / ಪ್ಯಾನ್ / ಮತದಾರರ ಗುರುತಿನ ಚೀಟಿ. ಸ್ಪಷ್ಟವಾಗಿ ಗೋಚರಿಸಬೇಕು.",
                "ಪಾಸ್‌ಪೋರ್ಟ್ ಗಾತ್ರದ ಭಾವಚಿತ್ರ: ಇತ್ತೀಚಿನ ಬಣ್ಣದ ಫೋಟೋ.",
                "ಆವರಣದ ಪುರಾವೆ: ಬಾಡಿಗೆ ಒಪ್ಪಂದ, ವಿದ್ಯುತ್ ಬಿಲ್, ಅಥವಾ ಮಾಲೀಕರಿಂದ ಎನ್‌ಒಸಿ."
            ],
            "action_plan": [
                "ನಿಮ್ಮ ಐಡಿ, ಫೋಟೋ ಮತ್ತು ಆವರಣದ ಪುರಾವೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ.",
                "ಅಧಿಕೃತ FoSCoS ಪೋರ್ಟಲ್‌ಗೆ ಭೇಟಿ ನೀಡಿ (foscos.fssai.gov.in).",
                "'Apply for License/Registration' ಆಯ್ಕೆಮಾಡಿ ಮತ್ತು ಫಾರ್ಮ್ A/B ಅನ್ನು ಭರ್ತಿ ಮಾಡಿ.",
                "ಶುಲ್ಕವನ್ನು ಪಾವತಿಸಿ (ಮೂಲ ನೋಂದಣಿಗೆ ₹100) ಮತ್ತು ಸಲ್ಲಿಸಿ."
            ],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ ಮತ್ತು ಅರ್ಜಿಯನ್ನು ಪ್ರಾರಂಭಿಸಿ."
        },
        "PM-KISAN Samman Nidhi": {
            "recommended_service": "ಪಿಎಂ-ಕಿಸಾನ್ ಸಮ್ಮಾನ್ ನಿಧಿ",
            "description": "ಎಲ್ಲಾ ಭೂಮಿ ಹೊಂದಿರುವ ರೈತ ಕುಟುಂಬಗಳಿಗೆ ವರ್ಷಕ್ಕೆ ₹6,000 ಆದಾಯ ಬೆಂಬಲ.",
            "eligibility_status": "ಅರ್ಹತೆ ದೃಢೀಕರಿಸಲ್ಪಟ್ಟಿದೆ",
            "eligibility_criteria": [
                "ಭೂಮಿ ಹೊಂದಿರುವ ರೈತ ಕುಟುಂಬವಾಗಿರಬೇಕು.",
                "ಸಾಗುವಳಿ ಭೂಮಿ ನಿಮ್ಮ ಹೆಸರಿನಲ್ಲಿ ನೋಂದಾಯಿತವಾಗಿರಬೇಕು.",
                "ಸಂಸ್ಥೆಯ ಭೂಮಾಲೀಕರು, ಪ್ರಸ್ತುತ/ಮಾಜಿ ಮಂತ್ರಿಗಳು ಅಥವಾ ಆದಾಯ ತೆರಿಗೆ ಪಾವತಿಸುವವರು ಆಗಿರಬಾರದು."
            ],
            "required_documents": [
                "ಆಧಾರ್ ಕಾರ್ಡ್: ಇ-ಕೆವೈಸಿಗೆ ಕಡ್ಡಾಯ.",
                "ಭೂ ಮಾಲೀಕತ್ವದ ದಾಖಲೆಗಳು: ಖತೌನಿ / ಪಟ್ಟಾ.",
                "ಬ್ಯಾಂಕ್ ಖಾತೆ ವಿವರಗಳು: ಆಧಾರ್ ಲಿಂಕ್ ಮಾಡಿದ ಸಕ್ರಿಯ ಬ್ಯಾಂಕ್ ಖಾತೆ."
            ],
            "action_plan": [
                "ನಿಮ್ಮ ಆಧಾರ್ ಮತ್ತು ಭೂ ದಾಖಲೆಗಳನ್ನು ಸಿದ್ಧವಾಗಿಟ್ಟುಕೊಳ್ಳಿ.",
                "pmkisan.gov.in ಗೆ ಭೇಟಿ ನೀಡಿ ಮತ್ತು 'New Farmer Registration' ಕ್ಲಿಕ್ ಮಾಡಿ.",
                "ಆಧಾರ್ ಒಟಿಪಿ ಮೂಲಕ ಇ-ಕೆವಿಸಿ ಪೂರ್ಣಗೊಳಿಸಿ.",
                "ಭೂಮಿ ವಿವರಗಳನ್ನು ಸಲ್ಲಿಸಿ ಮತ್ತು ಪರಿಶೀಲನೆಗಾಗಿ ಕಾಯಿರಿ."
            ],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ ಮತ್ತು ಇ-ಕೆವಿಸಿ ಪೂರ್ಣಗೊಳಿಸಿ."
        },
        "National Scholarship Portal": {
            "recommended_service": "ರಾಷ್ಟ್ರೀಯ ವಿದ್ಯಾರ್ಥಿವೇತನ ಪೋರ್ಟಲ್ (NSP)",
            "description": "ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ಎಲ್ಲಾ ಸರ್ಕಾರಿ ವಿದ್ಯಾರ್ಥಿವೇತನಗಳ ಏಕೈಕ ತಾಣ.",
            "eligibility_status": "ಅರ್ಹತೆ ದೃಢೀಕರಿಸಲ್ಪಟ್ಟಿದೆ",
            "eligibility_criteria": [
                "ಭಾರತದ ಪ್ರಜೆಯಾಗಿರಬೇಕು.",
                "ಮಾನ್ಯತೆ ಪಡೆದ ಶಿಕ್ಷಣ ಸಂಸ್ಥೆಯಲ್ಲಿ ದಾಖಲಾಗಿರಬೇಕು.",
                "ಯೋಜನೆಯ ಆಧಾರದ ಮೇಲೆ ಆದಾಯ ಮತ್ತು ಶೈಕ್ಷಣಿಕ ಅರ್ಹತೆ ಅನ್ವಯಿಸುತ್ತದೆ."
            ],
            "required_documents": [
                "ಆಧಾರ್ ಕಾರ್ಡ್: ಮೊಬೈಲ್ ಮತ್ತು ಬ್ಯಾಂಕ್‌ಗೆ ಲಿಂಕ್ ಆಗಿರಬೇಕು.",
                "ಹಿಂದಿನ ವರ್ಷದ ಅಂಕಪಟ್ಟಿ: ಶೈಕ್ಷಣಿಕ ಪ್ರಗತಿಯ ಪುರಾವೆ.",
                "ಆದಾಯ / ಜಾತಿ ಪ್ರಮಾಣಪತ್ರ: ಸಮರ್ಥ ಪ್ರಾಧಿಕಾರದಿಂದ ನೀಡಲ್ಪಟ್ಟಿರಬೇಕು."
            ],
            "action_plan": [
                "scholarships.gov.in ನಲ್ಲಿ ನಿಮ್ಮ ಆಧಾರ್ ಬಳಸಿ ನೋಂದಾಯಿಸಿ.",
                "ಲಾಗಿನ್ ಆಗಿ ಸಾಮಾನ್ಯ ಅರ್ಜಿ ನಮೂನೆಯನ್ನು ಭರ್ತಿ ಮಾಡಿ.",
                "ಅಗತ್ಯ ದಾಖಲೆಗಳ ಸ್ಕ್ಯಾನ್ ಪ್ರತಿಗಳನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.",
                "ಪರಿಶೀಲನೆಗಾಗಿ ಸಂಸ್ಥೆಗೆ ಸಲ್ಲಿಸಿ."
            ],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ ಮತ್ತು ನೋಂದಣಿ ಪ್ರಾರಂಭಿಸಿ."
        },
        "Udyam Registration": {
            "recommended_service": "MSME ಉದ್ಯಮ ನೋಂದಣಿ",
            "description": "ಸೂಕ್ಷ್ಮ, ಸಣ್ಣ ಮತ್ತು ಮಧ್ಯಮ ಉದ್ಯಮಗಳಿಗೆ ಉಚಿತ ಸರ್ಕಾರಿ ನೋಂದಣಿ.",
            "eligibility_status": "ಅರ್ಹತೆ ದೃಢೀಕರಿಸಲ್ಪಟ್ಟಿದೆ",
            "eligibility_criteria": [
                "ಸೂಕ್ಷ್ಮ, ಸಣ್ಣ ಅಥವಾ ಮಧ್ಯಮ ಉದ್ಯಮವನ್ನು ಸ್ಥಾಪಿಸಲು ಇಚ್ಛಿಸುವ ಯಾವುದೇ ವ್ಯಕ್ತಿ.",
                "ಹೂಡಿಕೆ ಮತ್ತು ವಹಿವಾಟಿನ ಸ್ವಯಂ ಘೋಷಣೆಯ ಆಧಾರದ ಮೇಲೆ ಮಾತ್ರ."
            ],
            "required_documents": [
                "ಆಧಾರ್ ಕಾರ್ಡ್: ಒಟಿಪಿ ಪರಿಶೀಲನೆಗಾಗಿ ಮೊಬೈಲ್ ನಂಬರ್ ಲಿಂಕ್ ಆಗಿರಬೇಕು.",
                "ಪ್ಯಾನ್ ಕಾರ್ಡ್: ವ್ಯವಹಾರ ಅಥವಾ ವೈಯಕ್ತಿಕ ಪ್ಯಾನ್.",
                "ಬ್ಯಾಂಕ್ ಖಾತೆ ವಿವರಗಳು: ಖಾತೆ ಸಂಖ್ಯೆ ಮತ್ತು ಐಎಫ್‌ಎಸ್‌ಸಿ ಕೋಡ್."
            ],
            "action_plan": [
                "udyamregistration.gov.in ಗೆ ಭೇಟಿ ನೀಡಿ.",
                "ಆಧಾರ್ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ ಮತ್ತು ಒಟಿಪಿ ಪರಿಶೀಲಿಸಿ.",
                "ಪ್ಯಾನ್ ವಿವರಗಳನ್ನು ಒದಗಿಸಿ, ವಿವರ ಭರ್ತಿ ಮಾಡಿ ಮತ್ತು ಸಲ್ಲಿಸಿ."
            ],
            "next_step": "ದಾಖಲೆಗಳನ್ನು ಸಂಗ್ರಹಿಸಿ ಮತ್ತು ಉದ್ಯಮ ನೋಂದಣಿ ಪ್ರಾರಂಭಿಸಿ."
        },
        "Document Verification": {
            "recommended_service": "ದಾಖಲೆ ಪರಿಶೀಲನೆ (Document Verification)",
            "description": "ದಾಖಲೆಗಳಲ್ಲಿನ ದೋಷಗಳು ಅಥವಾ ಅಸ್ಪಷ್ಟತೆಗಳ ಪತ್ತೆಗಾಗಿ ಎಐ ಸಹಾಯ.",
            "eligibility_status": "ಸಾರ್ವತ್ರಿಕ ಅರ್ಹತಾ ಪರಿಶೀಲನೆ",
            "eligibility_criteria": [
                "ವಿಶ್ಲೇಷಿಸಬೇಕಾದ ಯಾವುದೇ ದಾಖಲೆ ಅಥವಾ ಸರ್ಕಾರಿ ಪತ್ರ."
            ],
            "required_documents": [
                "ಪರಿಶೀಲನೆಗಾಗಿ ದಾಖಲೆ: ಪಿಡಿಎಫ್, ಪಿಎನ್‌ಜಿ ಅಥವಾ ಜೆಪಿಜಿ ರೂಪದಲ್ಲಿ."
            ],
            "action_plan": [
                "ನಿಮ್ಮ ದಾಖಲೆಯನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.",
                "ವಿಶ್ಲೇಷಣಾ ವರದಿಯನ್ನು ಪಡೆದು ಸೂಚನೆಗಳನ್ನು ಪಾಲಿಸಿ."
            ],
            "next_step": "ವಿಶ್ಲೇಷಣೆಗಾಗಿ ದಾಖಲೆ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ."
        }
    },
    "te": {
        "FSSAI Registration": {
            "recommended_service": "FSSAI రిజిస్ట్రేషన్ & లైసెన్సింగ్",
            "description": "భారతదేశంలోని అన్ని ఆహార సంబంధిత వ్యాపారాల కోసం అధికారిక నమోదు.",
            "eligibility_status": "అర్హత నిర్ధారించబడింది",
            "eligibility_criteria": [
                "ఆహార తయారీ, ప్రాసెసింగ్ లేదా విక్రయాలను నిర్వహించే ఏ వ్యక్తి అయినా.",
                "చిన్న ఆహార వ్యాపార నిర్వాహకులకు (టర్నోవర్ ₹12 లక్షల లోపు) ప్రాథమిక నమోదు అవసరం.",
                "ఆహార వ్యాపార టర్నోవర్ ₹12 లక్షల కంటే ఎక్కువ ఉంటే స్టేట్ లేదా సెంట్రల్ లైసెన్స్ అవసరం."
            ],
            "required_documents": [
                "ఫోటో ఐడి రుజువు: ఆధార్ / పాన్ / ఓటర్ ఐడి. స్పష్టంగా కనిపించాలి.",
                "పాసపోర్ట్ సైజు ఫోటో: ఇటీవల తీసిన రంగుల ఫోటో.",
                "ఆవరణల రుజువు: అద్దె ఒప్పందం, విద్యుత్ బిల్లు, లేదా యజమాని నుండి NOC."
            ],
            "action_plan": [
                "ఆవరణల రుజువు, ఫోటో, మరియు ఐడి సేకరించండి.",
                "అధికారిక FoSCoS పోర్టల్ (foscos.fssai.gov.in) సందర్శించండి.",
                "'Apply for License/Registration' ఎంచుకుని, ఫారమ్ A/B పూరించండి.",
                "ఫీజు చెల్లించి (ప్రాథమిక నమోదుకు ₹100) సమర్పించండి."
            ],
            "next_step": "పత్రాలను సేకరించి దరఖాస్తును ప్రారంభించండి."
        },
        "PM-KISAN Samman Nidhi": {
            "recommended_service": "పీఎం-కిసాన్ సమ్మాన్ నిధి",
            "description": "భూమి ఉన్న రైతు కుటుంబాలందరికీ సంవత్సరానికి ₹6,000 ఆర్థిక సహాయం.",
            "eligibility_status": "అర్హత నిర్ధారించబడింది",
            "eligibility_criteria": [
                "ఖచ్చితంగా భూమి కలిగిన రైతు కుటుంబం అయి ఉండాలి.",
                "సాగు భూమి మీ పేరు మీద నమోదై ఉండాలి.",
                "సంస్థాగత భూస్వాములు, ప్రజా ప్రతినిధులు, లేదా ఆదాయపు పన్ను చెల్లించేవారు కాకూడదు."
            ],
            "required_documents": [
                "ఆధార్ కార్డ్: ఇ-కేవైసీ కొరకు తప్పనిసరి.",
                "భూమి యాజమాన్య పత్రాలు: పట్టాదార్ పాస్ పుస్తకం / ఖతౌనీ.",
                "బ్యాంక్ ఖాతా వివరాలు: ఆధార్ అనుసంధానించబడిన బ్యాంక్ ఖాతా."
            ],
            "action_plan": [
                "మీ ఆధార్ మరియు భూమి పత్రాలను సిద్ధంగా ఉంచుకోండి.",
                "pmkisan.gov.in సందర్శించి 'New Farmer Registration' క్లిక్ చేయండి.",
                "ఆధార్ ఓటీపీ ద్వారా ఈ-కేవైసీ పూర్తి చేయండి.",
                "భూమి వివరాలను సమర్పించి ధృవీకరణ కొరకు వేచి ఉండండి."
            ],
            "next_step": "పత్రాలను సేకరించి ఈ-కేవైసీ పూర్తి చేయండి."
        },
        "National Scholarship Portal": {
            "recommended_service": "నేషనల్ స్కాలర్‌షిప్ పోర్టల్ (NSP)",
            "description": "విద్యార్థుల కోసం అన్ని రకాల ప్రభుత్వ స్కాలర్‌షిప్‌ల ఒకే వేదిక.",
            "eligibility_status": "అర్హత నిర్ధారించబడింది",
            "eligibility_criteria": [
                "భారతదేశ పౌరుడై ఉండాలి.",
                "గుర్తింపు పొందిన విద్యా సంస్థలో చదువుతూ ఉండాలి.",
                "ఎంచుకున్న పథకం ప్రకారం ఆదాయ మరియు విద్యా అర్హత పరిమితులు వర్తిస్తాయి."
            ],
            "required_documents": [
                "ఆధార్ కార్డ్: మొబైల్ నంబర్ మరియు బ్యాంక్‌తో లింక్ అయి ఉండాలి.",
                "క్రితం సంవత్సరం మార్కుల పత్రం: విద్యా ప్రగతి రుజువు.",
                "ఆదాయం / కుల ధృవీకరణ పత్రం: సంబంధిత అధికారి జారీ చేసినది."
            ],
            "action_plan": [
                "scholarships.gov.in లో మీ ఆధార్ ఉపయోగించి నమోదు చేసుకోండి.",
                "లాగిన్ అయి దరఖాస్తును పూర్తి చేయండి.",
                "అవసరమైన పత్రాల స్కాన్ చేసిన కాపీలను అప్‌లోడ్ చేయండి.",
                "ధృవీకరణ కొరకు మీ విద్యా సంస్థకు సమర్పించండి."
            ],
            "next_step": "పత్రాలను సేకరించి నమోదు ప్రారంభించండి."
        },
        "Udyam Registration": {
            "recommended_service": "MSME ఉద్యమ రిజిస్ట్రేషన్",
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
        "description": service_data.get("description", "Official government service."),
        "eligibility_status": eligibility["status"],
        "eligibility_criteria": service_data.get("eligibility", []),
        "required_documents": service_data.get("documents", docs["mandatory_documents"]),
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

frontend_dir = os.path.join(os.path.dirname(__file__), "..")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Starting NaviGo AI Layer Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
