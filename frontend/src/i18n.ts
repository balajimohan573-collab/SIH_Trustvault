// Trilingual layer: English / हिंदी / தமிழ்.
// Feeds every decision + reason + nav string shown to the user, and powers the
// browser-native voice (Web Speech) so the interface works for low-literacy users.

import { useEffect, useState } from 'react'

export type Lang = 'en' | 'hi' | 'ta'

export const LANGS: { id: Lang; label: string; short: string; tts: string }[] = [
  { id: 'en', label: 'English', short: 'EN', tts: 'en-IN' },
  { id: 'hi', label: 'हिंदी', short: 'हिं', tts: 'hi-IN' },
  { id: 'ta', label: 'தமிழ்', short: 'த', tts: 'ta-IN' },
]

const STORE_KEY = 'trustvault.lang'

const D: Record<string, Record<Lang, string>> = {
  tagline: {
    en: 'Verify once. Control access everywhere.',
    hi: 'एक बार सत्यापित करें, हर जगह पहुँच नियंत्रित करें।',
    ta: 'ஒருமுறை சரிபார்த்து, எல்லா இடங்களிலும் அணுகலைக் கட்டுப்படுத்துங்கள்।',
  },
  live: { en: 'Live', hi: 'लाइव', ta: 'நேரடி' },
  signout_tip: {
    en: 'Sign out of your current session (clears auth token and returns to login).',
    hi: 'अपने सत्र से बाहर निकलें (लॉगिन टोकन हटाकर लॉगिन पेज पर लौटें)।',
    ta: 'உங்கள் அமர்விலிருந்து வெளியேறவும் (நுழைவு டோக்கனை அழித்து உள்நுழைவுப் பக்கத்திற்கு திரும்பவும்).',
  },

  // Navigation (friendly, plain-language)
  nav_dashboard: { en: 'Home', hi: 'होम', ta: 'முகப்பு' },
  nav_verify: { en: 'Verify', hi: 'सत्यापित करें', ta: 'சரிபார்' },
  nav_trust: { en: 'Security check', hi: 'सुरक्षा जाँच', ta: 'பாதுகாப்பு சரிபார்ப்பு' },
  nav_timeline: { en: 'Activity', hi: 'गतिविधि', ta: 'செயல்பாடு' },
  nav_credentials: { en: 'My certificates', hi: 'मेरे प्रमाणपत्र', ta: 'என் சான்றிதழ்கள்' },
  nav_assets: { en: 'My documents', hi: 'मेरे दस्तावेज़', ta: 'என் ஆவணங்கள்' },
  nav_access: { en: 'Requests', hi: 'अनुरोध', ta: 'கோரிக்கைகள்' },
  nav_audit: { en: 'History', hi: 'इतिहास', ta: 'வரலாறு' },

  // Decisions (friendly — hidden machinery underneath)
  dec_ALLOW: { en: 'Allowed', hi: 'अनुमति मिली', ta: 'அனுமதிக்கப்பட்டது' },
  dec_STEP_UP: {
    en: 'Needs more checking',
    hi: 'और जाँच चाहिए',
    ta: 'மேலும் சரிபார்ப்பு தேவை',
  },
  dec_RESTRICTED: {
    en: 'Limited access',
    hi: 'सीमित पहुँच',
    ta: 'வரம்புடன் அணுகல்',
  },
  dec_DENY: { en: 'Blocked', hi: 'रोका गया', ta: 'தடுக்கப்பட்டது' },

  decHit_ALLOW: {
    en: 'You can proceed.',
    hi: 'आप आगे बढ़ सकते हैं।',
    ta: 'நீங்கள் தொடரலாம்.',
  },
  decHit_STEP_UP: {
    en: 'One more quick check is needed.',
    hi: 'एक बार और त्वरित जाँच चाहिए।',
    ta: 'மேலும் ஒரு விரைவான சரிபார்ப்பு தேவை.',
  },
  decHit_RESTRICTED: {
    en: 'You can only read this for now.',
    hi: 'अभी आप इसे केवल पढ़ सकते हैं।',
    ta: 'இப்போது இதை படிக்க மட்டுமே முடியும்.',
  },
  decHit_DENY: {
    en: 'This was blocked. The reason is below.',
    hi: 'इसे रोक दिया गया। कारण नीचे है।',
    ta: 'இது தடுக்கப்பட்டது. காரணம் கீழே உள்ளது.',
  },

  // Reason codes (plain-language, low-literacy friendly)
  r_OK_CREDENTIAL: {
    en: 'Your identity certificate is valid.',
    hi: 'आपका सत्यापन प्रमाणपत्र सही है।',
    ta: 'உங்கள் சான்றிதழ் சரியாக உள்ளது.',
  },
  r_OK: { en: 'All checks passed.', hi: 'सभी जाँचें पास।', ta: 'அனைத்து சோதனைகளும் நிறைவேறின.' },
  r_UNAUTHENTICATED: { en: 'You are not signed in.', hi: 'आप लॉगिन नहीं हैं।', ta: 'நீங்கள் உள்நுழையவில்லை.' },
  r_NO_CREDENTIAL: {
    en: 'No identity certificate found.',
    hi: 'कोई सत्यापन प्रमाणपत्र नहीं मिला।',
    ta: 'சான்றிதழ் எதுவும் இல்லை.',
  },
  r_CREDENTIAL_REVOKED: {
    en: 'Your certificate has been cancelled.',
    hi: 'आपका प्रमाणपत्र रद्द हो चुका है।',
    ta: 'உங்கள் சான்றிதழ் ரத்து செய்யப்பட்டது.',
  },
  r_NEW_DEVICE: {
    en: 'This request is from a new device.',
    hi: 'यह नई डिवाइस से अनुरोध है।',
    ta: 'இது புதிய சாதனத்திலிருந்து வரும் கோரிக்கை.',
  },
  r_DEVICE_REVOKED: {
    en: 'This device has been cancelled.',
    hi: 'यह डिवाइस रद्द हो चुकी है।',
    ta: 'இந்த சாதனம் ரத்து செய்யப்பட்டது.',
  },
  r_KNOWN_DEVICE: {
    en: 'This is a device we know.',
    hi: 'यह आपकी जानी-पहचानी डिवाइस है।',
    ta: 'இது உங்களுக்கு தெரிந்த சாதனம்.',
  },
  r_NO_DEVICE_TRACKING: {
    en: 'No device information was available.',
    hi: 'डिवाइस की जानकारी नहीं मिली।',
    ta: 'சாதனத் தகவல் கிடைக்கவில்லை.',
  },
  r_REQUEST_VELOCITY_HIGH: {
    en: 'Too many requests are coming in.',
    hi: 'बहुत ज़्यादा अनुरोध हो रहे हैं।',
    ta: 'மிக அதிக கோரிக்கைகள் வருகின்றன.',
  },
  r_REQUEST_VELOCITY_EXCESSIVE: {
    en: 'Requests crossed a safe limit.',
    hi: 'अनुरोध सीमा से अधिक हो गए।',
    ta: 'கோரிக்கைகள் வரம்பை மீறின.',
  },
  r_UNUSUAL_HOUR: {
    en: 'The request is at an unusual time.',
    hi: 'असामान्य समय पर अनुरोध।',
    ta: 'வழக்கத்திற்கு மாறான நேரத்தில் கோரிக்கை.',
  },
  r_ANOMALY_DETECTED: {
    en: 'The AI watch saw something unusual.',
    hi: 'एआई ने असामान्यता देखी।',
    ta: 'AI அசாதாரண நிலையை கண்டறிந்தது.',
  },
  r_HISTORY_NORMAL: {
    en: 'Account history looks normal.',
    hi: 'खाता इतिहास सामान्य है।',
    ta: 'கணக்கு வரலாறு இயல்பாக உள்ளது.',
  },
  r_HISTORY_ANOMALOUS: {
    en: 'Recent activity looks unusual.',
    hi: 'हाल में असामान्य गतिविधि मिली।',
    ta: 'சமீபத்தில் அசாதாரண செயல்பாடு.',
  },
  r_NO_POLICY_FOR_ROLE: {
    en: 'There is no permission rule for this task.',
    hi: 'इस कार्य के लिए अनुमति नियम नहीं है।',
    ta: 'இந்தப் பணிக்கு அனுமதி விதி இல்லை.',
  },
  r_WRONG_PURPOSE: {
    en: 'The stated reason (purpose) is not allowed.',
    hi: 'अनुमति का कारण (उद्देश्य) गलत है।',
    ta: 'அனுமதியின் நோக்கம் தவறானது.',
  },
  r_NO_VALID_GRANT: {
    en: 'There is no active permission.',
    hi: 'कोई सक्रिय अनुमति नहीं है।',
    ta: 'செயலில் அனுமதி இல்லை.',
  },
  r_GRANT_EXPIRED: {
    en: 'The permission time has ended.',
    hi: 'अनुमति की अवधि समाप्त हो गई।',
    ta: 'அனுமதி காலம் முடிந்தது.',
  },
  r_ADMIN_OVERRIDE: {
    en: 'An administrator gave special permission.',
    hi: 'प्रशासक ने विशेष अनुमति दी।',
    ta: 'நிர்வாகி சிறப்பு அனுமதி வழங்கினார்.',
  },
  r_NON_ADMIN_OVERRIDE_ATTEMPT: {
    en: 'Special access was tried without permission.',
    hi: 'बिना अनुमति के विशेष पहुँच की कोशिश।',
    ta: 'அனுமதியின்றி சிறப்பு அணுகல் முயற்சி.',
  },
  r_TRUST_TOO_LOW: {
    en: 'The trust score is too low.',
    hi: 'विश्वास स्कोर कम है।',
    ta: 'நம்பிக்கை மதிப்பெண் குறைவு.',
  },
  r_LOCATION_MISMATCH: {
    en: 'Your location is not right for this document.',
    hi: 'स्थान इस दस्तावेज़ के लिए सही नहीं है।',
    ta: 'இருப்பிடம் இந்த ஆவணத்திற்கு சரியாக இல்லை.',
  },
  r_LOCATION_MISSING: {
    en: 'Location information was not given.',
    hi: 'स्थान की जानकारी नहीं दी गई।',
    ta: 'இருப்பிடத் தகவல் அளிக்கப்படவில்லை.',
  },
  r_TIME_OUTSIDE: {
    en: 'This is not permission time right now.',
    hi: 'अभी अनुमति का समय नहीं है।',
    ta: 'இப்போது அனுமதி நேரம் இல்லை.',
  },
  r_CONTEXT_REQUIRED: {
    en: 'More information is needed.',
    hi: 'अतिरिक्त जानकारी ज़रूरी है।',
    ta: 'கூடுதல் தகவல் தேவை.',
  },
  r_RESTRICTED_ACCESS: {
    en: 'Access is limited to read-only.',
    hi: 'पहुँच केवल पढ़ने तक सीमित।',
    ta: 'அணுகல் படிப்பதற்கு மட்டுமே.',
  },
  r_DURESS_ACTIVE: {
    en: 'Access is frozen for safety reasons.',
    hi: 'सुरक्षा कारणों से पहुँच रोकी गई।',
    ta: 'பாதுகாப்பு காரணங்களால் அணுகல் நிறுத்தப்பட்டது.',
  },

  // Verify screen
  verify_title: { en: 'Verify a credential QR', hi: 'प्रमाणपत्र QR सत्यापित करें', ta: 'சான்றிதழ் QR சரிபார்க்கவும்' },
  verify_valid: { en: 'VALID', hi: 'सही', ta: 'சரியானது' },
  verify_invalid: { en: 'INVALID', hi: 'गलत', ta: 'தவறானது' },
  verify_none: { en: 'No verification yet', hi: 'अभी कोई सत्यापन नहीं', ta: 'இன்னும் சரிபார்ப்பு இல்லை' },
  verify_btn: { en: 'Verify credential', hi: 'प्रमाणपत्र सत्यापित करें', ta: 'சான்றிதழை சரிபார்க்கவும்' },
  verify_btn_busy: { en: 'Verifying…', hi: 'सत्यापन हो रहा है…', ta: 'சரிபார்க்கிறது…' },
  verify_registered: {
    en: 'Registered — standing as a known credential.',
    hi: 'पंजीकृत — जानी-मानी प्रमाणपत्र है।',
    ta: 'பதிவு செய்யப்பட்டது — அறியப்பட்ட சான்றிதழ்.',
  },
  verify_ok: { en: 'Active — available for use.', hi: 'सक्रिय — उपयोग के लिए तैयार।', ta: 'செயலில் — பயன்படுத்தத் தயார்.' },
  verify_revoked: { en: 'Revoked — no longer usable.', hi: 'रद्द — अब उपयोग नहीं हो सकता।', ta: 'ரத்து — இனி பயன்படுத்த முடியாது.' },
  verify_invalid_token: {
    en: 'The token is missing, tampered with, or expired. The document they claim does not match.',
    hi: 'टोकन गायब, बदला हुआ या समाप्त है।',
    ta: 'டோக்கன் இல்லை, மாற்றப்பட்டது அல்லது காலாவதியானது.',
  },
  verify_result_title: { en: 'Verification result', hi: 'सत्यापन परिणाम', ta: 'சரிபார்ப்பு முடிவு' },
  verify_result_sub: {
    en: 'Umbrella result: real or fake. Details below stay minimal on purpose.',
    hi: 'एक ही परिणाम: असली या नकली। विवरण जान-बूझकर सीमित रखे गए हैं।',
    ta: 'முடிவு: உண்மையானது அல்லது போலியானது. விவரங்கள் வேண்டுமென்றே குறைவாகவே வைக்கப்படுகின்றன.',
  },
  verify_paste: {
    en: 'Paste the short-lived token the holder generated',
    hi: 'होल्डर द्वारा बनाया गया अल्पकालिक टोकन डालें',
    ta: 'உரிமையாளர் உருவாக்கிய குறுகியகால டோக்கனை ஒட்டவும்',
  },
  speak_button: { en: 'Listen', hi: 'सुनें', ta: 'கேளுங்கள்' },
  // Access screen — three big buttons
  allow: { en: 'Allow', hi: 'अनुमति दें', ta: 'அனுமதி' },
  ask_again: { en: 'Ask again', hi: 'फिर पूछें', ta: 'மறுபடியும் கேள்' },
  block: { en: 'Block', hi: 'रोकें', ta: 'தடு' },
  allow_hit: { en: 'Grant created. They can view it until it expires.', hi: 'अनुमति दी गई। समाप्ति तक वे देख सकेंगे।', ta: 'அனுமதி வழங்கப்பட்டது. காலம் முடியும் வரை அவரால் பார்க்க முடியும்.' },
  ask_again_hit: { en: 'Denied for now. Ask them to try again later.', hi: 'अभी अस्वीकृत। बाद में फिर पूछें।', ta: 'இப்போது மறுக்கப்பட்டது. பின்னர் மீண்டும் கேட்கவும்.' },
  block_hit: { en: 'Blocked. The request is closed.', hi: 'रोका गया। अनुरोध बंद हो गया।', ta: 'தடுக்கப்பட்டது. கோரிக்கை முடிந்தது.' },
  approve_act: { en: 'Approve', hi: 'स्वीकृत', ta: 'ஏற்கவும்' },
  deny_act: { en: 'Deny', hi: 'अस्वीकृत', ta: 'மறுக்கவும்' },
  request_status: { en: 'new request for your document', hi: 'आपके दस्तावेज़ के लिए अनुरोध', ta: 'உங்கள் ஆவணத்திற்கான கோரிக்கை' },
  status_pending: { en: 'pending', hi: 'लंबित', ta: 'நிலுவையில்' },
  status_approved: { en: 'approved', hi: 'स्वीकृत', ta: 'ஏற்கப்பட்டது' },
  status_denied: { en: 'denied', hi: 'अस्वीकृत', ta: 'மறுக்கப்பட்டது' },

  // Onboarding walkthrough — read aloud on first login
  onboard_title: { en: 'Welcome to TrustVault', hi: 'TrustVault में आपका स्वागत है', ta: 'TrustVault-க்கு வரவேற்கிறோம்' },
  onboard_sub: {
    en: 'Worth over a minute — it reads itself.',
    hi: 'एक मिनट ज़रूर दें — यह खुद बोलता है।',
    ta: 'ஒரு நிமிடம் தாருங்கள் — அது தானே பேசுகிறது.',
  },
  onboard_script: {
    en: 'Welcome to TrustVault. Your identity is safe here. You can verify a document with the QR scanner, watch your trust score, and approve access with three big buttons: Allow, Ask again, or Block. If you are ever under threat, one tap on Duress freezes your identity silently. Every request you approve is time-bound and recorded on the blockchain. Let us get started.',
    hi: 'TrustVault में आपका स्वागत है। आपकी पहचान यहाँ सुरक्षित है। आप QR स्कैनर से दस्तावेज़ सत्यापित कर सकते हैं, अपना विश्वास स्कोर देख सकते हैं, और तीन बड़े बटन — अनुमति दें, फिर पूछें, या रोकें — से अनुमति दे सकते हैं। अगर कभी आप पर दबाव हो, तो एक टैप में ड्यूरेस आपकी पहचान को चुपचाप फ्रीज़ कर देता है। आप जो भी अनुमति देते हैं वह समय-सीमित होती है और ब्लॉकचेन पर दर्ज होती है। चलिए, शुरू करते हैं।',
    ta: 'TrustVault-க்கு வரவேற்கிறோம். உங்கள் அடையாளம் இங்கே பாதுகாப்பானது. QR ஸ்கேனர் மூலம் ஆவணங்களைச் சரிபார்க்கலாம், உங்கள் நம்பிக்கை மதிப்பெண்ணைப் பார்க்கலாம், அனுமதி, மறுபடியும் கேள், தடு — இந்த மூன்று பெரிய பொத்தான்களால் அனுமதி வழங்கலாம். ஒருபோதும் ஆபத்தில் இருந்தால், ஒரே தொடுதலில் டூரஸ் உங்கள் அடையாளத்தை அமைதியாக உறைய வைக்கும். நீங்கள் வழங்கும் அனைத்து அனுமதிகளும் கால வரம்புடையவை, பிளாக்செயினில் பதிவாகும். தொடங்குவோம்.',
  },
  onboard_start: { en: 'Got it — let me in', hi: 'समझ गया — अंदर ले चलें', ta: 'சரி — என்னை உள்ளே அனுப்பு' },
  onboard_replay: { en: 'Play tour again', hi: 'टूर फिर से सुनें', ta: 'விளக்கத்தை மீண்டும் கேளுங்கள்' },

  // Home screen — plain language, zero jargon
  home_welcome: { en: 'Welcome!', hi: 'आपका स्वागत है!', ta: 'வரவேற்கிறோம்!' },
  home_sub: {
    en: 'Everything below is handled safely for you — no setup, no keys, no confusing settings.',
    hi: 'नीचे सब कुछ आपके लिए सुरक्षित रूप से संभाला जाता है — न कोई सेटअप, न कोई चाबियाँ, न कोई जटिल स्क्रिप्ट।',
    ta: 'கீழே உள்ள அனைத்தும் உங்களுக்காகப் பாதுகாப்பாக நிர்வகிக்கப்படுகிறது — எந்த அமைப்பும் இல்லை, சாவிகள் இல்லை.',
  },
  home_security: { en: 'Security check', hi: 'सुरक्षा जाँच', ta: 'பாதுகாப்பு சரிபார்ப்பு' },
  home_security_line: {
    en: 'Your account is in good shape right now.',
    hi: 'आपका खाता अभी ठीक है।',
    ta: 'உங்கள் கணக்கு இப்போது நல்ல நிலையில் உள்ளது.',
  },
  home_certs: { en: 'My certificates', hi: 'मेरे प्रमाणपत्र', ta: 'என் சான்றிதழ்கள்' },
  home_docs: { en: 'My documents', hi: 'मेरे दस्तावेज़', ta: 'என் ஆவணங்கள்' },
  home_requests: { en: 'Requests for my documents', hi: 'मेरे दस्तावेज़ों के अनुरोध', ta: 'என் ஆவணங்களுக்கான கோரிக்கைகள்' },
  home_none: { en: 'nothing yet', hi: 'अभी कुछ नहीं', ta: 'இன்னும் எதுவும் இல்லை' },
  home_activity: { en: 'Recent activity', hi: 'हाल की गतिविधि', ta: 'சமீபத்திய செயல்பாடு' },
  home_quick: { en: 'What would you like to do?', hi: 'आप क्या करना चाहेंगे?', ta: 'நீங்கள் என்ன செய்ய விரும்புகிறீர்கள்?' },
  act_add_cert: { en: 'Add a certificate', hi: 'प्रमाणपत्र जोड़ें', ta: 'சான்றிதழைச் சேர்க்க' },
  act_add_cert_hint: {
    en: 'A school, university or office adds it for you once.',
    hi: 'स्कूल, विश्वविद्यालय या दफ्तर इसे एक बार जोड़ देता है।',
    ta: 'பள்ளி, பல்கலைக்கழகம் அல்லது அலுவலகம் அதை ஒருமுறை சேர்க்கும்.',
  },
  act_store_doc: { en: 'Store a document', hi: 'दस्तावेज़ रखें', ta: 'ஆவணத்தைச் சேமிக்க' },
  act_store_doc_hint: {
    en: 'Upload anything important. It is locked safely.',
    hi: 'कोई भी ज़रूरी चीज़ अपलोड करें। यह सुरक्षित रूप से बंद रहती है।',
    ta: 'முக்கியமானதை பதிவேற்றுங்கள். அது பாதுகாப்பாகப் பூட்டப்படும்.',
  },
  act_share: { en: 'Share a proof', hi: 'प्रमाण साझा करें', ta: 'சான்றைப் பகிர' },
  act_share_hint: {
    en: 'Make a short-lived QR that proves a certificate is real.',
    hi: 'एक अल्पकालिक QR बनाएँ जो साबित करे कि प्रमाणपत्र असली है।',
    ta: 'சான்றிதழ் உண்மையானது என நிரூபிக்கும் குறுகியகால QR உருவாக்கவும்.',
  },
  act_check: { en: 'Check my security', hi: 'अपनी सुरक्षा जाँचें', ta: 'என் பாதுகாப்பைச் சரிபார்' },
  act_check_hint: {
    en: 'See how healthy your account is, right now.',
    hi: 'देखें कि आपका खाता अभी कितना सुरक्षित है।',
    ta: 'உங்கள் கணக்கு இப்போது எவ்வளவு பாதுகாப்பானது எனப் பார்க்கவும்.',
  },
  act_requests: { en: 'Handle requests', hi: 'अनुरोध संभालें', ta: 'கோரிக்கைகளைக் கையாள' },
  act_requests_hint: {
    en: 'Allow or block who can see your documents.',
    hi: 'देखें कि कौन आपके दस्तावेज़ देख सकता है और कौन नहीं।',
    ta: 'உங்கள் ஆவணங்களை யார் பார்க்கலாம் என்பதை அனுமதியுங்கள்.',
  },
  act_have: { en: 'You currently have', hi: 'आपके पास अभी हैं', ta: 'இப்போது உங்களிடம் உள்ளன' },
  certs_unit: { en: 'certificates', hi: 'प्रमाणपत्र', ta: 'சான்றிதழ்கள்' },
  docs_unit: { en: 'documents', hi: 'दस्तावेज़', ta: 'ஆவணங்கள்' },
  pending_unit: { en: 'pending requests', hi: 'लंबित अनुरोध', ta: 'நிலுவை கோரிக்கைகள்' },
}

export function tr(lang: Lang, key: string): string {
  return D[key]?.[lang] ?? D[key]?.en ?? key
}

export function getStoredLang(): Lang {
  try {
    const v = localStorage.getItem(STORE_KEY)
    return v === 'hi' || v === 'ta' ? v : 'en'
  } catch {
    return 'en'
  }
}

const LANG_EVENT = 'trustvault:lang'

export function storeLang(lang: Lang) {
  try {
    localStorage.setItem(STORE_KEY, lang)
  } catch {
    /* private mode */
  }
  window.dispatchEvent(new CustomEvent(LANG_EVENT, { detail: lang }))
}

export function useLang(): Lang {
  const [lang, setLang] = useState<Lang>(getStoredLang())
  useEffect(() => {
    const onLang = (e: Event) => setLang((e as CustomEvent<Lang>).detail ?? getStoredLang())
    window.addEventListener(LANG_EVENT, onLang)
    return () => window.removeEventListener(LANG_EVENT, onLang)
  }, [])
  return lang
}

export function speak(text: string, lang: Lang) {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
  try {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = LANGS.find((l) => l.id === lang)?.tts ?? 'en-IN'
    u.rate = 0.92
    const voices = window.speechSynthesis.getVoices()
    const voice = voices.find(
      (v) => v.lang.replace('_', '-').toLowerCase() === u.lang.toLowerCase(),
    )
    if (voice) u.voice = voice
    window.speechSynthesis.speak(u)
  } catch {
    /* voice unsupported */
  }
}