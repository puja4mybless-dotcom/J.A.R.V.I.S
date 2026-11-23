"""
J.A.R.V.I.S. Academic Intelligence Engine
==========================================
Covers all academic subjects from Class 1 (Primary) to IAS/UPSC level.

Subjects: Mathematics, Physics, Chemistry, Biology, History, Geography,
Civics/Polity, Economics, Computer Science, English, Hindi, Environmental
Science, Social Science, Accountancy, Business Studies, Psychology,
Sociology, Philosophy, and all UPSC/SSC/NEET/JEE topics.

Detects subject & level, formats structured step-by-step solutions, and
enriches the LLM prompt with subject-specific pedagogical context.
"""

import re
from typing import Optional

# ── Subject keyword maps ────────────────────────────────────────────────────

SUBJECT_MAP = {
    "mathematics": [
        "solve", "calculate", "equation", "algebra", "geometry", "trigonometry",
        "calculus", "derivative", "integral", "matrix", "determinant", "probability",
        "statistics", "arithmetic", "fraction", "percentage", "ratio", "lcm", "hcf",
        "prime", "factor", "quadratic", "linear", "polynomial", "coordinate",
        "permutation", "combination", "logarithm", "progression", "ap", "gp",
        "sets", "functions", "limits", "differentiation", "integration", "vector",
        "bodmas", "simplify", "expand", "pythagoras", "theorem", "proof", "axiom",
        "mean", "median", "mode", "variance", "standard deviation", "binomial",
        "number system", "decimal", "binary", "hexadecimal", "digit",
        "maths", "math", "ganit", "गणित",
    ],
    "physics": [
        "newton", "force", "velocity", "acceleration", "momentum", "energy",
        "work", "power", "gravity", "gravitational", "ohm", "resistance", "current",
        "voltage", "capacitor", "inductor", "magnet", "magnetic", "electric",
        "light", "refraction", "reflection", "lens", "mirror", "optics",
        "wave", "frequency", "wavelength", "amplitude", "doppler", "sound",
        "thermodynamics", "entropy", "heat", "temperature", "pressure", "gas",
        "nuclear", "radioactive", "fission", "fusion", "quantum", "photon",
        "relativity", "einstein", "semiconductor", "transistor", "diode",
        "circuit", "kirchhoff", "faraday", "electromagnetic", "induction",
        "kinematics", "dynamics", "motion", "projectile", "satellite", "orbit",
        "buoyancy", "archimedes", "viscosity", "surface tension", "bernoulli",
        "physics", "bhautiki", "भौतिकी",
    ],
    "chemistry": [
        "atom", "molecule", "element", "compound", "mixture", "bond", "ionic",
        "covalent", "metallic", "reaction", "acid", "base", "salt", "ph",
        "oxidation", "reduction", "redox", "electrolysis", "electrochemistry",
        "periodic table", "valency", "electron", "proton", "neutron", "isotope",
        "mole", "molarity", "molality", "normality", "titration", "buffer",
        "organic", "inorganic", "hydrocarbon", "alkane", "alkene", "alkyne",
        "benzene", "aromatic", "polymer", "monomer", "carbohydrate", "protein",
        "lipid", "amino acid", "dna", "rna", "enzyme", "catalyst", "activation",
        "enthalpy", "entropy", "gibbs", "rate of reaction", "equilibrium",
        "le chatelier", "haber", "contact process", "faraday", "colligative",
        "chemistry", "rasayan", "रसायन",
    ],
    "biology": [
        "cell", "nucleus", "membrane", "mitochondria", "chloroplast", "ribosome",
        "dna", "rna", "gene", "chromosome", "genetics", "heredity", "mendel",
        "evolution", "darwin", "natural selection", "mutation", "adaptation",
        "ecosystem", "food chain", "food web", "biodiversity", "biome",
        "photosynthesis", "respiration", "digestion", "circulation", "heart",
        "blood", "nervous system", "brain", "neuron", "hormone", "endocrine",
        "reproduction", "fertilization", "embryo", "placenta", "germination",
        "plant", "root", "stem", "leaf", "flower", "pollination", "seed",
        "bacteria", "virus", "fungi", "algae", "protozoa", "nematode",
        "immunity", "antibody", "antigen", "vaccine", "disease", "pathogen",
        "taxonomy", "classification", "kingdom", "phylum", "class", "order",
        "neet", "zoology", "botany", "biology", "jeev vigyan", "जीव विज्ञान",
    ],
    "history": [
        "ancient", "medieval", "modern", "civilization", "dynasty", "empire",
        "mughal", "british", "colonial", "independence", "revolt", "war",
        "battle", "treaty", "revolution", "french", "american", "world war",
        "harappa", "vedic", "maurya", "gupta", "maratha", "rajput", "sultanate",
        "akbar", "ashoka", "gandhi", "nehru", "bose", "tilak", "rani laxmi",
        "partition", "constitution", "swadeshi", "non-cooperation", "quit india",
        "renaissance", "reformation", "industrial revolution", "imperialism",
        "colonialism", "nationalism", "fascism", "nazism", "communism",
        "un", "cold war", "nato", "vietnam", "korean", "suez", "cuban",
        "history", "itihas", "इतिहास",
    ],
    "geography": [
        "latitude", "longitude", "meridian", "equator", "tropic", "arctic",
        "continent", "ocean", "river", "mountain", "plateau", "plain", "delta",
        "desert", "forest", "climate", "monsoon", "rainfall", "humidity",
        "soil", "erosion", "weathering", "volcano", "earthquake", "tsunami",
        "tectonic", "lithosphere", "atmosphere", "hydrosphere", "biosphere",
        "population", "migration", "urbanization", "density", "census",
        "india map", "states", "capitals", "rivers of india", "himalayas",
        "deccan", "western ghats", "eastern ghats", "brahmaputra", "ganges",
        "yamuna", "indus", "natural resources", "minerals", "coal", "petroleum",
        "agriculture", "crop", "irrigation", "industry", "transport", "trade",
        "world geography", "physical geography", "human geography",
        "geography", "bhugol", "भूगोल",
    ],
    "civics_polity": [
        "constitution", "fundamental rights", "directive principles", "duties",
        "parliament", "lok sabha", "rajya sabha", "president", "prime minister",
        "supreme court", "high court", "panchayati raj", "local government",
        "federalism", "separation of powers", "judicial review", "pil",
        "amendment", "articles", "schedule", "preamble", "sovereignty",
        "democracy", "republic", "secularism", "socialism", "franchise",
        "election", "election commission", "adult suffrage", "voter id",
        "political party", "coalition", "cabinet", "council of ministers",
        "governor", "chief minister", "legislature", "executive", "judiciary",
        "ias", "ips", "ifs", "upsc", "civil services", "bureaucracy",
        "polity", "civics", "nagarik shastra", "नागरिक शास्त्र",
    ],
    "economics": [
        "demand", "supply", "price", "market", "gdp", "gnp", "inflation",
        "deflation", "stagflation", "recession", "depression", "boom", "slump",
        "fiscal", "monetary", "budget", "deficit", "surplus", "debt",
        "tax", "gst", "income tax", "direct tax", "indirect tax", "customs",
        "bank", "rbi", "credit", "debit", "interest", "loan", "investment",
        "capital", "labour", "land", "entrepreneurship", "production",
        "consumption", "savings", "expenditure", "imports", "exports",
        "trade balance", "current account", "bop", "foreign exchange",
        "liberalization", "privatization", "globalization", "lpg",
        "five year plan", "niti aayog", "planning commission", "poverty",
        "unemployment", "inequality", "human development index", "hdi",
        "microeconomics", "macroeconomics", "elasticity", "utility",
        "economics", "arthashastra", "अर्थशास्त्र",
    ],
    "computer_science": [
        "algorithm", "data structure", "array", "linked list", "stack", "queue",
        "tree", "graph", "sorting", "searching", "binary search", "bubble sort",
        "merge sort", "quick sort", "time complexity", "space complexity",
        "oop", "class", "object", "inheritance", "polymorphism", "encapsulation",
        "abstraction", "interface", "exception", "recursion", "dynamic programming",
        "database", "sql", "nosql", "normalization", "dbms", "er diagram",
        "operating system", "process", "thread", "deadlock", "scheduling",
        "memory management", "virtual memory", "paging", "segmentation",
        "networking", "tcp", "ip", "http", "https", "dns", "router", "switch",
        "cybersecurity", "encryption", "firewall", "malware", "phishing",
        "python", "java", "c++", "html", "css", "javascript", "programming",
        "compiler", "interpreter", "assembler", "machine code", "binary",
        "computer science", "computer", "cs",
    ],
    "english": [
        "grammar", "noun", "pronoun", "verb", "adjective", "adverb",
        "conjunction", "preposition", "interjection", "sentence", "clause",
        "phrase", "tense", "active voice", "passive voice", "narration",
        "direct speech", "indirect speech", "essay", "letter", "paragraph",
        "comprehension", "unseen passage", "poetry", "prose", "drama",
        "literary devices", "metaphor", "simile", "alliteration", "rhyme",
        "synonyms", "antonyms", "one word", "idiom", "phrase", "proverb",
        "spelling", "punctuation", "vocabulary",
    ],
    "environmental_science": [
        "environment", "ecology", "pollution", "air pollution", "water pollution",
        "soil pollution", "noise pollution", "ozone", "greenhouse", "global warming",
        "climate change", "deforestation", "afforestation", "conservation",
        "wildlife", "endangered", "extinct", "biodiversity", "ecosystem",
        "natural disaster", "flood", "drought", "cyclone", "earthquake",
        "renewable energy", "solar", "wind", "biomass", "hydropower",
        "sustainable development", "carbon footprint", "recycling",
        "evs", "paryavaran",
    ],
    "social_science": [
        "social", "society", "community", "culture", "caste", "class",
        "gender", "religion", "tribe", "urban", "rural", "development",
        "poverty", "inequality", "welfare", "rights", "duties",
        "secularism", "democracy", "social science", "samaj shastra",
    ],
}

# ── Level detection ─────────────────────────────────────────────────────────

LEVEL_PATTERNS = {
    "primary": [
        r"\bclass\s*[1-5]\b", r"\bgrade\s*[1-5]\b", r"\bstandard\s*[1-5]\b",
        r"\b(first|second|third|fourth|fifth)\s+(class|grade|standard)\b",
        r"\bprimary\b", r"\bkindergarten\b", r"\belementary\b",
    ],
    "middle": [
        r"\bclass\s*[6-8]\b", r"\bgrade\s*[6-8]\b", r"\bstandard\s*[6-8]\b",
        r"\b(sixth|seventh|eighth)\s+(class|grade|standard)\b",
        r"\bmiddle school\b",
    ],
    "secondary": [
        r"\bclass\s*[9]|10\b", r"\bgrade\s*9|10\b",
        r"\b(ninth|tenth)\s+(class|grade|standard)\b",
        r"\bssc\b", r"\bmatric\b", r"\bsecondary\b", r"\bboard exam\b",
    ],
    "higher_secondary": [
        r"\bclass\s*1[12]\b", r"\bgrade\s*1[12]\b",
        r"\b(eleventh|twelfth)\s+(class|grade|standard)\b",
        r"\bhsc\b", r"\bintermediate\b", r"\bplus two\b", r"\b\+2\b",
        r"\bjee\b", r"\bneet\b", r"\b12th\b", r"\b11th\b",
    ],
    "undergraduate": [
        r"\bbsc\b", r"\bba\b", r"\bbcom\b", r"\bbtec?h?\b",
        r"\bundergraduate\b", r"\bcollege\b", r"\bdegree\b",
        r"\bsemester\b", r"\bhonours?\b",
    ],
    "competitive": [
        r"\bupsc\b", r"\bias\b", r"\bips\b", r"\bifs\b",
        r"\bcivil service\b", r"\bssc\s+cgl\b", r"\bssc\s+chsl\b",
        r"\brailway\b", r"\brrb\b", r"\bbank(?:ing)?\s+exam\b",
        r"\bstate\s+psc\b", r"\bmpsc\b", r"\bppsc\b", r"\bkpsc\b",
        r"\bcat\b", r"\bmat\b", r"\bgmat\b", r"\bgre\b",
        r"\bdefence\b", r"\bnda\b", r"\bcds\b",
    ],
}

# ── Academic system prompt injections per subject ──────────────────────────

SUBJECT_SYSTEM_PROMPTS = {
    "mathematics": (
        "You are J.A.R.V.I.S., the world's most precise mathematics engine. "
        "For numerical problems: show EVERY step clearly, explain each operation. "
        "Format: Problem → Formula → Step-by-Step → Final Answer → Verification. "
        "For conceptual questions: define, explain with example, then summarize. "
        "Use clean notation. Never skip steps. If a diagram is needed, describe it textually."
    ),
    "physics": (
        "You are J.A.R.V.I.S., a precision physics analyzer. "
        "For numerical problems: State given values → Identify formula → Substitute → Solve → Units check. "
        "For conceptual questions: State the principle → Explain mechanism → Real-world example. "
        "Always mention SI units. Mention relevant scientists and laws."
    ),
    "chemistry": (
        "You are J.A.R.V.I.S., a master chemistry intelligence. "
        "For reactions: Write balanced equation → Explain type (synthesis/decomposition/etc.) → State conditions. "
        "For conceptual questions: Define → Mechanism → Example → Application. "
        "Always mention oxidation states, bond types, or electronic configurations where relevant."
    ),
    "biology": (
        "You are J.A.R.V.I.S., a comprehensive biology knowledge base. "
        "Explain biological processes step by step. "
        "Mention: cellular level → organ level → organism level → ecosystem level where applicable. "
        "Use NCERT-aligned terminology. Mention relevant experiments (Mendel, Watson & Crick, etc.)."
    ),
    "history": (
        "You are J.A.R.V.I.S., a master historian with encyclopedic knowledge. "
        "Structure answer as: Time Period → Context → Key Events → Key Figures → Causes → Effects → Significance. "
        "For UPSC/IAS: include multiple perspectives, economic/social/political dimensions. "
        "Cite key dates, treaties, and movements accurately."
    ),
    "geography": (
        "You are J.A.R.V.I.S., a geographic intelligence system. "
        "For physical geography: explain processes (erosion, plate tectonics, etc.) with causes & effects. "
        "For human geography: include data, distribution patterns, regional examples. "
        "For India geography: use district/state context, rivers, climate zones, resources."
    ),
    "civics_polity": (
        "You are J.A.R.V.I.S., a constitutional and political science expert. "
        "For polity questions: cite exact Article numbers, Schedules, and Amendments. "
        "Explain the structure → function → significance chain. "
        "For UPSC: include recent amendments, landmark Supreme Court cases, and committee reports."
    ),
    "economics": (
        "You are J.A.R.V.I.S., an economics intelligence engine. "
        "For theory: Define → Explain model → Graph description → Real-world application. "
        "For India economy: use current data (GDP, inflation, budget figures). "
        "For UPSC: cover both micro and macro aspects, government schemes, and economic surveys."
    ),
    "computer_science": (
        "You are J.A.R.V.I.S., an advanced computing intelligence. "
        "For algorithms: provide pseudocode or code snippet → time/space complexity → example trace. "
        "For conceptual questions: define → mechanism → advantage/disadvantage → use case. "
        "Format code in proper indentation. Mention programming language if relevant."
    ),
    "english": (
        "You are J.A.R.V.I.S., an English language and literature expert. "
        "For grammar: state the rule → give examples → show correct vs incorrect. "
        "For literature: discuss theme, character, literary devices, and context. "
        "For writing: provide a structured template with example."
    ),
    "environmental_science": (
        "You are J.A.R.V.I.S., an environmental science expert. "
        "Cover: causes → effects → solutions → global/national policy context. "
        "Mention relevant conventions (Kyoto, Paris Agreement, etc.) and Indian laws (Wildlife Protection Act, etc.)."
    ),
    "default": (
        "You are J.A.R.V.I.S., an academic assistant covering many subjects. Be clear about uncertainty and do not invent facts. "
        "from Class 1 to IAS/UPSC professional level. "
        "Provide thorough, accurate, step-by-step explanations. "
        "Match the complexity to the student's level. Use examples. Never hallucinate facts."
    ),
}


class AcademicEngine:
    """
    Detects subject and academic level from a query, then returns
    an enriched system prompt injection for the LLM to give a
    detailed, pedagogically appropriate answer.
    """

    @staticmethod
    def detect_subject(query: str) -> str:
        """Returns the best-matching academic subject key, or 'default'."""
        q = query.lower()
        scores = {}
        for subject, keywords in SUBJECT_MAP.items():
            count = sum(1 for kw in keywords if kw in q)
            if count > 0:
                scores[subject] = count
        if not scores:
            return "default"
        return max(scores, key=scores.get)

    @staticmethod
    def detect_level(query: str) -> str:
        """Returns the detected academic level string."""
        q = query.lower()
        for level, patterns in LEVEL_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, q):
                    return level
        # Infer by complexity heuristics
        competitive_words = ["upsc", "ias", "ips", "ifs", "civil service", "ssc cgl", "gate", "cat", "neet", "jee advanced"]
        if any(w in q for w in competitive_words):
            return "competitive"
        advanced_words = ["derivative", "integration", "quantum", "organic chemistry", "genetics", "thermodynamics",
                          "relativity", "nuclear", "semiconductor", "data structure", "algorithm", "constitution"]
        if any(w in q for w in advanced_words):
            return "higher_secondary"
        return "general"

    @staticmethod
    def is_academic_query(query: str) -> bool:
        """Returns True if the query looks like an academic/study question."""
        q = query.lower()

        # Direct academic intent phrases
        academic_phrases = [
            "explain", "define", "what is", "how does", "why does", "describe",
            "solve", "calculate", "prove", "derive", "differentiate between",
            "compare", "difference between", "example of", "types of",
            "causes of", "effects of", "importance of", "advantages of",
            "concept of", "theory of", "law of", "principle of",
            "samjhao", "samjha", "batao", "bata", "kya hai", "kaise kaam karta",
            "question", "answer", "exam", "study", "learn", "teach",
            "class", "grade", "chapter", "topic", "subject",
            # Historical/factual question words that imply academic lookup
            "who was", "who were", "who is", "who are",
            "when did", "when was", "when were",
            "where did", "where was",
            "how was", "how did",
            "why did", "why was",
            "what happened", "what caused", "what led",
        ]
        if any(phrase in q for phrase in academic_phrases):
            return True

        # Subject keyword match (need at least 1 strong academic keyword)
        strong_academic_keywords = [
            # Physics
            "newton", "ohm", "faraday", "kirchhoff", "gravitational", "electromagnetic",
            "thermodynamics", "kinematics", "quantum", "relativity",
            # Chemistry
            "periodic table", "covalent", "ionic", "titration", "oxidation", "reduction",
            "enthalpy", "equilibrium", "organic", "inorganic",
            # Biology
            "photosynthesis", "mitosis", "meiosis", "dna", "rna", "genetics",
            "ecosystem", "evolution", "chloroplast", "mitochondria",
            # History
            "dynasty", "empire", "revolt", "revolution", "independence", "partition",
            "mughal", "british raj", "colonial", "maurya", "gupta",
            # Geography
            "latitude", "longitude", "monsoon", "tectonic", "erosion", "delta",
            # Polity
            "constitution", "parliament", "fundamental rights", "preamble",
            "lok sabha", "rajya sabha", "supreme court",
            # Economics
            "gdp", "inflation", "fiscal", "monetary", "microeconomics", "macroeconomics",
            # Math
            "quadratic", "pythagoras", "differentiation", "integration", "probability",
            "permutation", "combination", "logarithm",
        ]
        if any(kw in q for kw in strong_academic_keywords):
            return True

        # Subject keyword match (broader — need 2+ matches)
        for keywords in SUBJECT_MAP.values():
            if sum(1 for kw in keywords if kw in q) >= 2:
                return True

        return False

    @classmethod
    def build_academic_prompt(cls, query: str, user_name: str = "Sir") -> dict:
        """
        Returns a dict with:
        - subject: detected subject
        - level: detected level
        - system_injection: specialized system prompt to prepend
        - formatted_query: cleaned query to send to LLM
        """
        subject = cls.detect_subject(query)
        level = cls.detect_level(query)

        level_instructions = {
            "primary": "The student is in Class 1–5 (primary school). Use very simple language, short sentences, fun examples. Avoid jargon.",
            "middle": "The student is in Class 6–8 (middle school). Use clear simple language with examples. Introduce basic terminology.",
            "secondary": "The student is in Class 9–10 (secondary/SSC board). Use NCERT-level explanation, include formulas and diagrams (described textually).",
            "higher_secondary": "The student is in Class 11–12 / JEE / NEET level. Provide deep conceptual + numerical explanation. Include derivations where relevant.",
            "undergraduate": "The student is at undergraduate college level. Provide comprehensive academic-level explanation with references to standard textbooks.",
            "competitive": "The student is preparing for UPSC/IAS/SSC/Banking/State PSC competitive exams. Provide comprehensive, multi-dimensional, exam-oriented answer with facts, figures, examples, and current affairs where relevant.",
            "general": "Provide a thorough, well-structured explanation suitable for a motivated learner.",
        }

        subject_prompt = SUBJECT_SYSTEM_PROMPTS.get(subject, SUBJECT_SYSTEM_PROMPTS["default"])
        level_prompt = level_instructions.get(level, level_instructions["general"])

        system_injection = (
            f"{subject_prompt}\n\n"
            f"[ACADEMIC LEVEL]: {level_prompt}\n\n"
            f"[FORMAT]: Structure your answer with clear headings if needed. "
            f"Use numbered steps for processes/solutions. "
            f"End with a brief summary or key takeaway. "
            f"Address the user as '{user_name}'."
        )

        return {
            "subject": subject,
            "level": level,
            "system_injection": system_injection,
            "formatted_query": query.strip(),
        }

    @classmethod
    def get_offline_academic_response(cls, query: str, user_name: str = "Sir", lang: str = "en") -> Optional[str]:
        """
        Returns a quick offline response for very common academic facts
        (without needing LLM API). Used as instant fallback.
        """
        q = query.lower().strip()

        # Quick math facts
        quick_facts = {
            "speed of light": f"The speed of light in vacuum is exactly 299,792,458 metres per second (approximately 3 × 10⁸ m/s), {user_name}. This is denoted by 'c' and is the universal speed limit according to Einstein's Special Theory of Relativity.",
            "newton's first law": f"Newton's First Law of Motion (Law of Inertia), {user_name}: 'Every object continues in its state of rest or uniform motion in a straight line unless acted upon by an external unbalanced force.' Key concept: Inertia is the tendency of objects to resist change in their state of motion.",
            "newton's second law": f"Newton's Second Law of Motion, {user_name}: Force = Mass × Acceleration (F = ma). The rate of change of momentum of a body is directly proportional to the applied force and takes place in the direction of the force.",
            "newton's third law": f"Newton's Third Law of Motion, {user_name}: 'For every action, there is an equal and opposite reaction.' Both forces act on different bodies simultaneously. Example: When you push a wall, the wall pushes back with equal force.",
            "pythagoras theorem": f"The Pythagorean Theorem, {user_name}: In a right-angled triangle, the square of the hypotenuse equals the sum of squares of the other two sides. Formula: c² = a² + b², where 'c' is the hypotenuse.",
            "ohm's law": f"Ohm's Law, {user_name}: The current through a conductor is directly proportional to the voltage across it (at constant temperature). Formula: V = IR, where V = Voltage (Volts), I = Current (Amperes), R = Resistance (Ohms).",
            "preamble": f"The Preamble of the Indian Constitution, {user_name}: 'WE, THE PEOPLE OF INDIA, having solemnly resolved to constitute India into a SOVEREIGN SOCIALIST SECULAR DEMOCRATIC REPUBLIC and to secure to all its citizens: JUSTICE, LIBERTY, EQUALITY and to promote among them all FRATERNITY.' It was amended by the 42nd Constitutional Amendment (1976) to add 'Socialist' and 'Secular'.",
            "photosynthesis": f"Photosynthesis, {user_name}: The process by which green plants synthesize food using sunlight. Equation: 6CO₂ + 6H₂O + Light Energy → C₆H₁₂O₆ (Glucose) + 6O₂. It occurs in chloroplasts. Light reactions happen in thylakoids; dark reactions (Calvin Cycle) happen in stroma.",
            "mitosis": f"Mitosis, {user_name}: A type of cell division resulting in two daughter cells with the SAME number of chromosomes as the parent cell. Phases: Prophase → Metaphase → Anaphase → Telophase → Cytokinesis. It is used for growth, repair, and asexual reproduction.",
            "meiosis": f"Meiosis, {user_name}: A type of cell division resulting in four daughter cells with HALF the number of chromosomes (haploid). Occurs in two stages: Meiosis I (separates homologous chromosomes) and Meiosis II (separates sister chromatids). Used in formation of gametes (eggs & sperm).",
            "gdp": f"GDP (Gross Domestic Product), {user_name}: The total monetary value of all final goods and services produced within a country's borders in a specific time period (usually a year). GDP = C + I + G + (X - M), where C=Consumption, I=Investment, G=Government Spending, X=Exports, M=Imports.",
            "fundamental rights": f"The Six Fundamental Rights of Indian Citizens, {user_name}: (1) Right to Equality (Articles 14-18), (2) Right to Freedom (Articles 19-22), (3) Right against Exploitation (Articles 23-24), (4) Right to Freedom of Religion (Articles 25-28), (5) Cultural and Educational Rights (Articles 29-30), (6) Right to Constitutional Remedies (Article 32) — called the 'Heart and Soul' of the Constitution by Dr. B.R. Ambedkar.",
        }

        for key, response in quick_facts.items():
            if key in q:
                if lang in ("hi", "hinglish"):
                    return f"J.A.R.V.I.S. Academic Database se: {response}"
                return response

        return None


# Subject display names for UI/logging
SUBJECT_DISPLAY = {
    "mathematics": "📐 Mathematics",
    "physics": "⚛️ Physics",
    "chemistry": "🧪 Chemistry",
    "biology": "🧬 Biology",
    "history": "📜 History",
    "geography": "🌍 Geography",
    "civics_polity": "⚖️ Civics & Polity",
    "economics": "💹 Economics",
    "computer_science": "💻 Computer Science",
    "english": "📖 English",
    "environmental_science": "🌿 Environmental Science",
    "social_science": "🏛️ Social Science",
    "default": "🎓 Academic",
}
