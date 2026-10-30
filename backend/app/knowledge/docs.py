"""Seed knowledge base for Ask Sara. Each entry keeps its source and last-verified date so Sara can cite it.
Rules change often: re-verify before relying on them for a live launch."""

VERIFIED = "2026-10-30"

DOCS = [
    dict(id="ilp-arunachal", title="Inner Line Permit for Arunachal Pradesh", tags=["permit", "arunachal", "tawang", "ziro", "ilp"],
         text="Indian citizens who are not residents of Arunachal Pradesh need an Inner Line Permit (ILP) to enter the state, "
              "including Tawang, Ziro, Bomdila and Dirang. The e-ILP can be applied for online on the Arunachal Pradesh "
              "government portal with an ID proof and photo; carry printed and digital copies. Foreign nationals need a "
              "Protected Area Permit (PAP).",
         source="Arunachal Pradesh e-ILP portal (eilp.arunachal.gov.in)"),
    dict(id="ilp-northeast", title="Inner Line Permits for Nagaland, Mizoram and Manipur", tags=["permit", "nagaland", "mizoram", "manipur", "ilp", "hornbill"],
         text="Nagaland, Mizoram and Manipur also use the Inner Line Permit system for visitors from other states. Apply "
              "online on the respective state portals before travel. Rules for Nagaland ILP also apply during the Hornbill "
              "Festival in Kohima in December.",
         source="State government ILP portals"),
    dict(id="ladakh-permit", title="Ladakh protected-area permits", tags=["permit", "ladakh", "leh", "nubra", "pangong", "tso moriri"],
         text="Visits to protected areas of Ladakh such as Nubra Valley, Pangong Tso, Tso Moriri, Hanle and Turtuk require a "
              "permit and an environment / wildlife fee, available online through the Leh district administration portal. "
              "Spend at least 48 hours in Leh to acclimatise before going higher.",
         source="Leh district administration permit portal"),
    dict(id="sikkim-permit", title="Sikkim permits (Nathu La, Tsomgo, North Sikkim)", tags=["permit", "sikkim", "gangtok", "nathula", "tsomgo", "gurudongmar"],
         text="Indian tourists do not need a permit to enter Sikkim, but protected areas such as Tsomgo Lake, Nathu La, "
              "Yumthang and Gurudongmar need permits, usually arranged through registered tour operators in Gangtok with ID "
              "and photos. Foreigners need a Restricted Area Permit to enter Sikkim.",
         source="Sikkim Tourism"),
    dict(id="rann-permit", title="White Rann of Kutch permit", tags=["permit", "kutch", "rann", "gujarat", "dhordo"],
         text="A permit is required to visit the White Rann near Dhordo. It can be obtained online or at the Bhirandiyara "
              "checkpoint on the way. Rann Utsav tent city runs roughly November to February.",
         source="Gujarat Tourism"),
    dict(id="tatkal", title="IRCTC Tatkal booking basics", tags=["train", "irctc", "tatkal", "booking"],
         text="Tatkal tickets open one day before the journey date (excluding the journey day): AC classes at 10:00 AM and "
              "non-AC classes at 11:00 AM. Tatkal booking on IRCTC requires an Aadhaar-verified account with OTP "
              "authentication. Confirmed Tatkal tickets are generally not refundable on cancellation.",
         source="https://www.irctc.co.in"),
    dict(id="waitlist", title="Train waitlist types (GNWL, RLWL, PQWL, RAC)", tags=["train", "waitlist", "wl", "rac", "pnr"],
         text="GNWL (general waitlist) has the best chance of confirmation because it covers the full route. RLWL and PQWL "
              "are quotas for intermediate stations and confirm less often. RAC lets you board and share a berth. Waitlisted "
              "e-tickets that remain fully waitlisted after charting are cancelled automatically with a refund minus a small "
              "clerkage charge.",
         source="https://www.irctc.co.in"),
    dict(id="train-cancel", title="Train ticket cancellation and refunds", tags=["train", "cancel", "refund", "irctc"],
         text="Cancellation charges on confirmed tickets depend on class and how close to departure you cancel; charges rise "
              "closer to departure, and refunds are generally not available after charting for confirmed tickets. Check the "
              "current IRCTC refund rules before cancelling.",
         source="https://www.irctc.co.in"),
    dict(id="fog", title="North India fog season", tags=["fog", "winter", "delhi", "train", "delay", "north"],
         text="From mid-December to January dense fog across the Indo-Gangetic plains (Delhi, Punjab, UP, Bihar) regularly "
              "delays trains by several hours and disrupts early-morning flights. Keep large buffers between connections and "
              "prefer afternoon flights.",
         source="IMD seasonal advisories"),
    dict(id="monsoon", title="Monsoon travel in the hills", tags=["monsoon", "landslide", "himachal", "uttarakhand", "rain", "rafting"],
         text="During the south-west monsoon (roughly June to September) landslides frequently block roads in Himachal Pradesh, "
              "Uttarakhand, Sikkim and the North-East. Rafting in Rishikesh usually pauses in July–August. Keep a buffer day and "
              "watch IMD alerts.",
         source="IMD / state disaster management"),
    dict(id="char-dham", title="Char Dham Yatra registration", tags=["char dham", "kedarnath", "badrinath", "pilgrimage", "registration", "uttarakhand"],
         text="Pilgrims to Kedarnath, Badrinath, Gangotri and Yamunotri must register with the Uttarakhand Tourism Development "
              "Board before the yatra. The temples typically open around April–May and close around October–November. Book "
              "Kedarnath helicopter tickets only through the official IRCTC HeliYatra portal — fake helicopter booking sites "
              "are a common scam.",
         source="https://registrationandtouristcare.uk.gov.in"),
    dict(id="taj", title="Taj Mahal visiting rules", tags=["taj", "agra", "monument", "closed", "friday"],
         text="The Taj Mahal is closed to visitors every Friday. It opens around sunrise; sunrise visits have the fewest crowds. "
              "Large bags, food and tripods are not allowed inside. Buy tickets online from the ASI portal to skip queues.",
         source="Archaeological Survey of India (asi.gov.in)"),
    dict(id="digiyatra", title="DigiYatra at airports", tags=["airport", "digiyatra", "flight", "boarding"],
         text="DigiYatra lets domestic passengers pass airport entry and boarding gates using face recognition at supported "
              "airports. Register in the DigiYatra app with Aadhaar and link your boarding pass.",
         source="https://www.digiyatra.com"),
    dict(id="baggage", title="Domestic flight baggage", tags=["flight", "baggage", "luggage", "cabin"],
         text="Most Indian domestic economy fares include 7 kg of cabin baggage and around 15 kg of check-in baggage; some "
              "low-cost fares are cabin-only. Always check the fare rules shown at booking.",
         source="Airline fare rules"),
    dict(id="scams", title="Common travel scams", tags=["scam", "safety", "fraud", "helicopter", "taxi"],
         text="Avoid fake booking websites for Kedarnath helicopters, houseboats and hotels — book only through official or "
              "well-known platforms. Agree auto and taxi fares before starting or use metered / app cabs. Never share OTPs or "
              "UPI PINs with anyone claiming to be from a booking company.",
         source="Cyber crime advisories (cybercrime.gov.in)"),
    dict(id="app-booking", title="How booking works in Sara Explorer", tags=["app", "help", "book", "consent", "payment"],
         text="Choose options in Plan & Book or ask Sara. You get an approval card with the total price, cancellation terms and "
              "a price-hold timer. Press Approve & Pay to get one UPI QR code per vendor (airline, railway, hotel): you pay each "
              "vendor directly, then enter the 12-digit UPI reference (UTR). Each part of your trip is booked once that "
              "vendor confirms the money arrived. Track everything under My Trips.",
         source="Sara Explorer help"),
    dict(id="app-security", title="Account security in Sara Explorer", tags=["app", "help", "security", "login", "session", "password"],
         text="You stay signed in until your session ends. You can see every signed-in device under Account & Security and "
              "sign them out individually or all at once. Sara Explorer never asks for your password, OTP or UPI PIN in chat.",
         source="Sara Explorer help"),
    dict(id="app-sandbox", title="Demo mode", tags=["app", "help", "demo", "sandbox", "test", "payment"],
         text="This version is a demo: flights, trains and hotels come from a sandbox, so no real tickets are issued. "
              "Vendors are sample vendors with demo QR codes that cannot receive money — do not pay them.",
         source="Sara Explorer help"),
]
