import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from .config import settings
from .document_store import ensure_document_store


SOURCES_METADATA: Dict[str, Dict[str, Any]] = {
    "enterprise_supply_ops": {
        "source_id": "enterprise_supply_ops",
        "source_name": "Indian Enterprise Supply & Compliance DB",
        "filename": "enterprise_supply_ops.db",
        "description": (
            "Indian enterprise operations database featuring Reliance Industries, TCS, Infosys, L&T, "
            "Mahindra & Mahindra, Bharat Forge, Biocon, and Adani Green Energy across Gwalior, Jaipur, "
            "Mumbai, Morena, Ahmedabad/Gandhinagar, Ajmer, Katni, and Bhopal."
        ),
        "domain": "Indian Enterprise Supply Chain, Operations & Compliance",
    },
    "california_schools_bird_demo": {
        "source_id": "california_schools_bird_demo",
        "source_name": "Indian Regional Academies (BIRD Benchmark Schema)",
        "filename": "california_schools_bird_demo.db",
        "description": (
            "BIRD-compatible relational schema (schools, frpm, satscores) mapped across Gwalior, Jaipur, "
            "Mumbai, Morena, Ahmedabad/Gandhinagar, Ajmer, Katni, and Bhopal."
        ),
        "domain": "Education & Regional Policy (BIRD Text-to-SQL)",
    },
}


def get_db_path(source_id: str) -> Path:
    if source_id not in SOURCES_METADATA:
        raise ValueError(f"Unknown database source_id: {source_id}")
    return settings.DATA_DIR / SOURCES_METADATA[source_id]["filename"]


def get_graph_db_path() -> Path:
    return settings.DATA_DIR / "graph_store.db"


def get_meta_db_path() -> Path:
    return settings.DATA_DIR / "app_meta.db"


def ensure_sample_databases(force_reset: bool = False) -> None:
    """Initialize sample SQLite databases and persistent knowledge graph."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if force_reset:
        for p in [
            get_db_path("enterprise_supply_ops"),
            get_db_path("california_schools_bird_demo"),
            get_graph_db_path(),
        ]:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    try:
                        conn = sqlite3.connect(str(p))
                        cur = conn.cursor()
                        tbls = [
                            row[0]
                            for row in cur.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                            ).fetchall()
                        ]
                        for tbl in tbls:
                            cur.execute(f"DROP TABLE IF EXISTS [{tbl}]")
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
    _init_enterprise_db(get_db_path("enterprise_supply_ops"), force_reset=force_reset)
    _init_california_schools_db(get_db_path("california_schools_bird_demo"), force_reset=force_reset)
    _init_meta_db(get_meta_db_path())
    _init_graph_db(get_graph_db_path(), force_reset=force_reset)
    graph_conn = sqlite3.connect(str(get_graph_db_path()))
    ensure_document_store(graph_conn)
    graph_conn.commit()
    graph_conn.close()


def _init_enterprise_db(db_path: Path, force_reset: bool = False) -> None:
    if db_path.exists() and not force_reset:
        return
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    if force_reset:
        for tbl in ["incidents", "shipments", "procurement_contracts", "vendors", "facilities", "regions"]:
            cur.execute(f"DROP TABLE IF EXISTS [{tbl}]")
        conn.commit()
    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE regions (
            region_id TEXT PRIMARY KEY,
            region_name TEXT NOT NULL,
            headquarters_city TEXT NOT NULL,
            risk_tier TEXT NOT NULL,
            director_name TEXT NOT NULL
        );

        CREATE TABLE facilities (
            facility_id TEXT PRIMARY KEY,
            facility_name TEXT NOT NULL,
            region_id TEXT NOT NULL,
            facility_type TEXT NOT NULL,
            annual_budget_usd REAL NOT NULL,
            headcount INTEGER,
            FOREIGN KEY (region_id) REFERENCES regions(region_id)
        );

        CREATE TABLE vendors (
            vendor_id TEXT PRIMARY KEY,
            vendor_name TEXT NOT NULL,
            country TEXT NOT NULL,
            tier_level INTEGER NOT NULL,
            compliance_score REAL,
            contact_email TEXT,
            primary_product TEXT NOT NULL
        );

        CREATE TABLE procurement_contracts (
            contract_id TEXT PRIMARY KEY,
            vendor_id TEXT NOT NULL,
            facility_id TEXT NOT NULL,
            contract_value_usd REAL NOT NULL,
            status TEXT NOT NULL,
            signed_date TEXT NOT NULL,
            FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
            FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
        );

        CREATE TABLE shipments (
            shipment_id TEXT PRIMARY KEY,
            contract_id TEXT NOT NULL,
            vendor_id TEXT NOT NULL,
            facility_id TEXT NOT NULL,
            component_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            delay_days INTEGER NOT NULL,
            shipment_status TEXT NOT NULL,
            FOREIGN KEY (contract_id) REFERENCES procurement_contracts(contract_id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
            FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
        );

        CREATE TABLE quality_incidents (
            incident_id TEXT PRIMARY KEY,
            facility_id TEXT NOT NULL,
            vendor_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            financial_impact_usd REAL NOT NULL,
            reported_date TEXT NOT NULL,
            FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
        );
        """
    )

    # Regions built around the exact Indian cities selected by the user:
    # Gwalior, Morena, Katni, Bhopal, Jaipur, Ajmer, Ahmedabad / Gandhinagar, Mumbai
    regions = [
        ("REG-NORTH", "Region North (Gwalior-Morena-Jaipur-Ajmer)", "Jaipur", "LOW", "Rajeshwar Scindia"),
        ("REG-CENTRAL", "Region Central (Bhopal-Katni Belt)", "Bhopal", "LOW", "Ananya Deshmukh"),
        ("REG-WEST-GUJ", "Region West (Ahmedabad-Gandhinagar)", "Ahmedabad / Gandhinagar", "MEDIUM", "Vikramaditya Patel"),
        ("REG-WEST-MAH", "Region Coastal (Mumbai HQ)", "Mumbai", "HIGH", "Siddharth Mehta"),
    ]
    cur.executemany("INSERT INTO regions VALUES (?, ?, ?, ?, ?)", regions)

    facilities = [
        ("FAC-GWL", "Gwalior Precision Engineering Plant", "REG-NORTH", "Manufacturing", 18500000.0, 540),
        ("FAC-MRN", "Morena Solar & Agro-Logistics Hub", "REG-NORTH", "Assembly & Grid", 11200000.0, 260),
        ("FAC-JPR", "Jaipur Smart Grid & Digital Park", "REG-NORTH", "R&D & Grid", 24000000.0, 680),
        ("FAC-AJM", "Ajmer Heavy Traction & Forging Unit", "REG-NORTH", "Manufacturing", 15400000.0, 390),
        ("FAC-BPL", "Bhopal Bio-Pharma & Electricals Complex", "REG-CENTRAL", "Bio-Manufacturing", 21800000.0, 610),
        ("FAC-KTN", "Katni Defense & Mineral Ordnance Hub", "REG-CENTRAL", "Heavy Metallurgy", 17000000.0, None),  # intentional NULL headcount for data quality test
        ("FAC-AMD", "Ahmedabad Gandhinagar GIFT Tech Tower", "REG-WEST-GUJ", "Cloud & FinTech", 29500000.0, 820),
        ("FAC-MUM", "Mumbai Refinery & Enterprise Core", "REG-WEST-MAH", "Refinery & Core", 36000000.0, 1150),
    ]
    cur.executemany("INSERT INTO facilities VALUES (?, ?, ?, ?, ?, ?)", facilities)

    # The exact 8 Indian companies selected by the user (+ 2 realistic ERP duplicate aliases for Entity Resolution)
    vendors = [
        ("VND-01", "Larsen & Toubro (L&T)", "Gwalior, India", 1, 95.5, "ops@larsentoubro.in", "Heavy Defense & Structural Turbines"),
        ("VND-02", "L&T Engineering Ltd.", "Gwalior, India", 1, 95.0, None, "Heavy Defense & Structural Turbines"),
        ("VND-03", "Bharat Forge", "Katni, India", 1, 93.5, "supply@bharatforge.in", "Artillery Barrels & Forged Crankshafts"),
        ("VND-04", "Adani Green Energy", "Morena, India", 2, 62.5, "grid@adanigreen.in", "High-Voltage Solar Inverter Arrays"),
        ("VND-05", "Mahindra & Mahindra", "Jaipur, India", 1, None, "fleet@mahindra.in", "Armored Utility Vehicles & Powertrains"),
        ("VND-06", "Reliance Industries", "Mumbai, India", 1, 97.2, "enterprise@ril.in", "Specialty Polymers & JioCloud Core"),
        ("VND-07", "Tata Consultancy Services (TCS)", "Ahmedabad / Gandhinagar, India", 1, 98.4, "gandhinagar@tcs.in", "Smart Grid Digital Twin & ERP"),
        ("VND-08", "Infosys", "Jaipur, India", 1, 96.0, "jaipur-dc@infosys.com", "AI Supply Chain Telemetry Suite"),
        ("VND-09", "Biocon", "Bhopal, India", 1, 91.8, "biologics@biocon.com", "Recombinant Enzymes & API Cold-Chain"),
    ]
    cur.executemany("INSERT INTO vendors VALUES (?, ?, ?, ?, ?, ?, ?)", vendors)

    # Note: CNT-904 shows Adani Green Energy as 'ACTIVE' in SQL, while Compliance Directive DOC-2026-04 marks it SUSPENDED (conflict verification!)
    contracts = [
        ("CNT-901", "VND-01", "FAC-GWL", 6400000.0, "ACTIVE", "2026-01-15"),
        ("CNT-902", "VND-02", "FAC-AJM", 2850000.0, "ACTIVE", "2026-02-10"),
        ("CNT-903", "VND-03", "FAC-KTN", 8900000.0, "ACTIVE", "2026-01-22"),
        ("CNT-904", "VND-04", "FAC-MRN", 5400000.0, "ACTIVE", "2026-03-05"),
        ("CNT-905", "VND-05", "FAC-JPR", 4100000.0, "UNDER_REVIEW", "2026-04-12"),
        ("CNT-906", "VND-06", "FAC-MUM", 12500000.0, "ACTIVE", "2026-02-28"),
        ("CNT-907", "VND-07", "FAC-AMD", 9200000.0, "ACTIVE", "2026-03-18"),
        ("CNT-908", "VND-08", "FAC-JPR", 5750000.0, "ACTIVE", "2026-04-02"),
        ("CNT-909", "VND-09", "FAC-BPL", 4950000.0, "ACTIVE", "2026-04-19"),
    ]
    cur.executemany("INSERT INTO procurement_contracts VALUES (?, ?, ?, ?, ?, ?)", contracts)

    shipments = [
        ("SHP-5001", "CNT-901", "VND-01", "FAC-GWL", "Heavy Defense & Structural Turbines", 120, 0, "DELIVERED"),
        ("SHP-5002", "CNT-902", "VND-02", "FAC-AJM", "Traction Gear Assemblies", 85, 2, "DELIVERED"),
        ("SHP-5003", "CNT-903", "VND-03", "FAC-KTN", "Artillery Barrels & Forged Crankshafts", 340, 7, "DELAYED"),
        ("SHP-5004", "CNT-904", "VND-04", "FAC-MRN", "High-Voltage Solar Inverter Arrays", 60, 14, "HELD_FOR_INSPECTION"),
        ("SHP-5005", "CNT-905", "VND-05", "FAC-JPR", "Armored Utility Vehicles & Powertrains", 95, 4, "DELAYED"),
        ("SHP-5006", "CNT-906", "VND-06", "FAC-MUM", "Specialty Polymers & JioCloud Core", 600, 0, "DELIVERED"),
        ("SHP-5007", "CNT-907", "VND-07", "FAC-AMD", "Smart Grid Digital Twin Nodes", 250, 0, "DELIVERED"),
        ("SHP-5008", "CNT-909", "VND-09", "FAC-BPL", "Recombinant Enzymes & API Cold-Chain", 180, 1, "DELIVERED"),
    ]
    cur.executemany("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?)", shipments)

    incidents = [
        ("INC-701", "FAC-MRN", "VND-04", "CRITICAL", "Transformer Thermal Failure at Morena Sub-Station", 1420000.0, "2026-08-14"),
        ("INC-702", "FAC-KTN", "VND-03", "HIGH", "Forging Batch 44 Micro-Stress Variance at Katni", 680000.0, "2026-09-02"),
        ("INC-703", "FAC-GWL", "VND-01", "LOW", "Calibration Drift on Gwalior Turbine Test Rig", 45000.0, "2026-07-19"),
        ("INC-704", "FAC-BPL", "VND-09", "MEDIUM", "Cold-Chain Excursion on Bhopal Highway Transit", 210000.0, "2026-09-18"),
    ]
    cur.executemany("INSERT INTO quality_incidents VALUES (?, ?, ?, ?, ?, ?, ?)", incidents)

    conn.commit()
    conn.close()


def _init_california_schools_db(db_path: Path, force_reset: bool = False) -> None:
    if db_path.exists() and not force_reset:
        return
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    if force_reset:
        for tbl in ["satscores", "frpm", "schools"]:
            cur.execute(f"DROP TABLE IF EXISTS [{tbl}]")
        conn.commit()
    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE schools (
            CDSCode TEXT PRIMARY KEY,
            School TEXT NOT NULL,
            County TEXT NOT NULL,
            City TEXT NOT NULL,
            Region TEXT NOT NULL,
            Charter INTEGER NOT NULL,
            FundingType TEXT,
            AdmFName1 TEXT,
            AdmLName1 TEXT
        );

        CREATE TABLE frpm (
            CDSCode TEXT PRIMARY KEY,
            AcademicYear TEXT NOT NULL,
            Enrollment_K12 INTEGER NOT NULL,
            FreeMealCount_K12 INTEGER NOT NULL,
            EligibleFreeRate_K12 REAL NOT NULL,
            FOREIGN KEY (CDSCode) REFERENCES schools(CDSCode)
        );

        CREATE TABLE satscores (
            cds TEXT PRIMARY KEY,
            sname TEXT NOT NULL,
            cname TEXT NOT NULL,
            NumTstTakr INTEGER NOT NULL,
            AvgScrRead INTEGER,
            AvgScrMath INTEGER,
            AvgScrWrite INTEGER,
            PctGE1500 REAL,
            FOREIGN KEY (cds) REFERENCES schools(CDSCode)
        );
        """
    )

    schools_data = [
        ("01612590130229", "School A (Scindia STEM Academy Gwalior)", "Gwalior District", "Gwalior", "Region North", 1, "Directly Funded", "Jordan", "Sharma"),
        ("19647330109884", "Jaipur National Charter High", "Jaipur District", "Jaipur", "Region North", 1, "Locally Funded", "Aditi", "Rathore"),
        ("37683383730017", "Mumbai Institute of Science Magnet", "Mumbai Suburban", "Mumbai", "Region West", 0, "State District", "Rohan", "Kulkarni"),
        ("38684783833241", "Gandhinagar GIFT Tech Preparatory", "Gandhinagar", "Ahmedabad / Gandhinagar", "Region West", 1, "Directly Funded", "Meera", "Desai"),
        ("43696664330585", "Bhopal Regional Science Academy", "Bhopal District", "Bhopal", "Region Central", 1, "Directly Funded", "Priya", "Verma"),
        ("34674393430112", "Ajmer & Katni Classical Vidyalaya", "Ajmer-Katni", "Ajmer", "Region North", 0, None, "Vikram", "Chauhan"),
    ]
    cur.executemany("INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", schools_data)

    frpm_data = [
        ("01612590130229", "2025-2026", 850, 544, 0.64),
        ("19647330109884", "2025-2026", 1120, 840, 0.75),
        ("37683383730017", "2025-2026", 1640, 295, 0.18),
        ("38684783833241", "2025-2026", 980, 412, 0.42),
        ("43696664330585", "2025-2026", 760, 190, 0.25),
        ("34674393430112", "2025-2026", 620, 341, 0.55),
    ]
    cur.executemany("INSERT INTO frpm VALUES (?, ?, ?, ?, ?)", frpm_data)

    sat_data = [
        ("01612590130229", "School A (Scindia STEM Academy Gwalior)", "Gwalior District", 210, 595, 642, 588, 78.5),
        ("19647330109884", "Jaipur National Charter High", "Jaipur District", 290, 540, 555, 532, 54.0),
        ("37683383730017", "Mumbai Institute of Science Magnet", "Mumbai Suburban", 480, 628, 665, 620, 86.2),
        ("38684783833241", "Gandhinagar GIFT Tech Preparatory", "Gandhinagar", 265, 580, 605, 575, 71.0),
        ("43696664330585", "Bhopal Regional Science Academy", "Bhopal District", 195, 612, 658, 604, 83.1),
        ("34674393430112", "Ajmer & Katni Classical Vidyalaya", "Ajmer-Katni", 150, 515, 510, 508, 42.0),
    ]
    cur.executemany("INSERT INTO satscores VALUES (?, ?, ?, ?, ?, ?, ?, ?)", sat_data)

    conn.commit()
    conn.close()


def _init_meta_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source_id TEXT NOT NULL,
            question TEXT,
            original_sql TEXT NOT NULL,
            executed_sql TEXT NOT NULL,
            execution_success INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            execution_time_ms REAL NOT NULL,
            repair_count INTEGER NOT NULL,
            validation_summary TEXT
        );

        CREATE TABLE IF NOT EXISTS evaluation_runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            dataset_mode TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            model_name TEXT NOT NULL,
            model_param_billions REAL NOT NULL,
            restricted_compliant INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            correct_count INTEGER NOT NULL,
            execution_accuracy REAL NOT NULL,
            avg_latency_ms REAL NOT NULL,
            failures_json TEXT NOT NULL,
            results_json TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _init_graph_db(db_path: Path, force_reset: bool = False) -> None:
    if db_path.exists() and not force_reset:
        return
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    if force_reset:
        for tbl in [
            "documents",
            "entities",
            "relationships",
            "entity_resolutions",
            "document_metadata",
            "document_terms",
            "document_claims",
        ]:
            cur.execute(f"DROP TABLE IF EXISTS [{tbl}]")
        conn.commit()
    cur.executescript(
        """
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE entities (
            id TEXT PRIMARY KEY,
            source_db TEXT NOT NULL,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            canonical_id TEXT,
            attributes_json TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_record TEXT NOT NULL,
            excerpt TEXT NOT NULL,
            extraction_method TEXT NOT NULL,
            confidence REAL NOT NULL,
            timestamp TEXT NOT NULL,
            is_merged INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE relationships (
            id TEXT PRIMARY KEY,
            source_db TEXT NOT NULL,
            source_entity_id TEXT NOT NULL,
            target_entity_id TEXT NOT NULL,
            rel_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_record TEXT NOT NULL,
            excerpt TEXT NOT NULL,
            extraction_method TEXT NOT NULL,
            confidence REAL NOT NULL,
            timestamp TEXT NOT NULL,
            is_inferred INTEGER NOT NULL DEFAULT 0,
            inference_rule TEXT
        );

        CREATE TABLE entity_resolutions (
            id TEXT PRIMARY KEY,
            duplicate_entity_id TEXT NOT NULL,
            canonical_entity_id TEXT NOT NULL,
            similarity_score REAL NOT NULL,
            reason TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    documents = [
        (
            "DOC-2026-01",
            "enterprise_supply_ops",
            "Gwalior, Jaipur & Ajmer Northern Corridor Industrial Audit",
            "audit_memo",
            (
                "Gwalior Precision Engineering Plant (FAC-GWL), Morena Solar & Agro-Logistics Hub (FAC-MRN), "
                "Jaipur Smart Grid & Digital Park (FAC-JPR), and Ajmer Heavy Traction & Forging Unit (FAC-AJM) "
                "operate in Region North under Director Rajeshwar Scindia. Larsen & Toubro (L&T) (also registered in "
                "legacy ERP as L&T Engineering Ltd.) supplies Heavy Defense & Structural Turbines to Gwalior Precision "
                "Engineering Plant under contract CNT-901, powering Project Mercury defense telemetry."
            ),
            "2026-09-10T10:00:00Z",
        ),
        (
            "DOC-2026-02",
            "enterprise_supply_ops",
            "Bhopal, Katni, Mumbai & Ahmedabad-Gandhinagar Enterprise Network Report",
            "risk_report",
            (
                "Katni Defense & Mineral Ordnance Hub (FAC-KTN) and Bhopal Bio-Pharma & Electricals Complex (FAC-BPL) "
                "operate in Region Central under Director Ananya Deshmukh. Bharat Forge (formally Bharat Forge Limited) "
                "supplies Artillery Barrels & Forged Crankshafts to Katni. Biocon supplies Recombinant Enzymes to Bhopal. "
                "In Mumbai, Reliance Industries powers Mumbai Refinery & Enterprise Core (FAC-MUM), while Tata Consultancy "
                "Services (TCS) and Infosys manage Smart Grid Digital Twin systems across Ahmedabad / Gandhinagar and Jaipur."
            ),
            "2026-09-20T14:30:00Z",
        ),
        (
            "DOC-2026-04",
            "enterprise_supply_ops",
            "Emergency Compliance Suspension: Adani Green Energy (Morena Sub-Station)",
            "compliance_directive",
            (
                "CRITICAL COMPLIANCE DIRECTIVE: Following Incident INC-701 (Transformer Thermal Failure at Morena Sub-Station) "
                "at Morena Solar & Agro-Logistics Hub (FAC-MRN) in Region North, vendor Adani Green Energy (VND-04) "
                "has been SUSPENDED immediately as of 2026-08-20. Note: Legacy SQL table procurement_contracts (CNT-904) "
                "still lists status = 'ACTIVE' due to ERP sync freeze."
            ),
            "2026-08-20T09:15:00Z",
        ),
        (
            "DOC-EDU-101",
            "california_schools_bird_demo",
            "Gwalior, Jaipur & Bhopal STEM Charter Accreditation & Quantum Initiative",
            "policy_brief",
            (
                "School A (Scindia STEM Academy Gwalior) is located in Region North (Gwalior) and is led by "
                "Principal Jordan Sharma. School A partners with Bhopal Regional Science Academy and Jaipur National "
                "Charter High under the Indian Quantum Curriculum Initiative."
            ),
            "2026-09-01T08:00:00Z",
        ),
    ]
    cur.executemany("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)", documents)

    ts = "2026-09-25T12:00:00Z"
    entities = [
        # Regions & Indian Cities (Locations)
        ("ENT-REG-NORTH", "enterprise_supply_ops", "Region North", "Location", None, json.dumps({"cities": "Gwalior, Morena, Jaipur, Ajmer", "hq": "Jaipur"}), "enterprise_supply_ops.regions", "database_record", "regions:REG-NORTH", "REG-NORTH | Region North (Gwalior, Morena, Jaipur, Ajmer) | Director: Rajeshwar Scindia", "structured_fk", 1.0, ts, 0),
        ("ENT-REG-CENTRAL", "enterprise_supply_ops", "Region Central", "Location", None, json.dumps({"cities": "Bhopal, Katni", "hq": "Bhopal"}), "enterprise_supply_ops.regions", "database_record", "regions:REG-CENTRAL", "REG-CENTRAL | Region Central (Bhopal, Katni) | Director: Ananya Deshmukh", "structured_fk", 1.0, ts, 0),
        ("ENT-REG-GUJ", "enterprise_supply_ops", "Ahmedabad / Gandhinagar", "Location", None, json.dumps({"state": "Gujarat", "region_id": "REG-WEST-GUJ"}), "enterprise_supply_ops.regions", "database_record", "regions:REG-WEST-GUJ", "REG-WEST-GUJ | Ahmedabad / Gandhinagar Twin-City Hub | Director: Vikramaditya Patel", "structured_fk", 1.0, ts, 0),
        ("ENT-REG-MUM", "enterprise_supply_ops", "Mumbai", "Location", None, json.dumps({"state": "Maharashtra", "region_id": "REG-WEST-MAH"}), "enterprise_supply_ops.regions", "database_record", "regions:REG-WEST-MAH", "REG-WEST-MAH | Mumbai Coastal HQ | Director: Siddharth Mehta", "structured_fk", 1.0, ts, 0),

        # Specific City Nodes for Gwalior, Morena, Jaipur, Ajmer, Bhopal, Katni
        ("ENT-CITY-GWL", "enterprise_supply_ops", "Gwalior", "Location", None, json.dumps({"state": "Madhya Pradesh"}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-GWL", "Gwalior Hub — Gwalior Precision Engineering Plant (FAC-GWL)", "structured_fk", 1.0, ts, 0),
        ("ENT-CITY-MRN", "enterprise_supply_ops", "Morena", "Location", None, json.dumps({"state": "Madhya Pradesh"}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-MRN", "Morena Hub — Morena Solar & Agro-Logistics Hub (FAC-MRN)", "structured_fk", 1.0, ts, 0),
        ("ENT-CITY-JPR", "enterprise_supply_ops", "Jaipur", "Location", None, json.dumps({"state": "Rajasthan"}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-JPR", "Jaipur Hub — Jaipur Smart Grid & Digital Park (FAC-JPR)", "structured_fk", 1.0, ts, 0),
        ("ENT-CITY-AJM", "enterprise_supply_ops", "Ajmer", "Location", None, json.dumps({"state": "Rajasthan"}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-AJM", "Ajmer Hub — Ajmer Heavy Traction & Forging Unit (FAC-AJM)", "structured_fk", 1.0, ts, 0),
        ("ENT-CITY-BPL", "enterprise_supply_ops", "Bhopal", "Location", None, json.dumps({"state": "Madhya Pradesh"}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-BPL", "Bhopal Hub — Bhopal Bio-Pharma & Electricals Complex (FAC-BPL)", "structured_fk", 1.0, ts, 0),
        ("ENT-CITY-KTN", "enterprise_supply_ops", "Katni", "Location", None, json.dumps({"state": "Madhya Pradesh"}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-KTN", "Katni Hub — Katni Defense & Mineral Ordnance Hub (FAC-KTN)", "structured_fk", 1.0, ts, 0),

        # People / Regional Directors
        ("ENT-PER-ELENA", "enterprise_supply_ops", "Rajeshwar Scindia", "Person", None, json.dumps({"role": "Regional Director (Gwalior-Jaipur)"}), "enterprise_supply_ops.regions", "database_record", "regions:REG-NORTH", "Director Rajeshwar Scindia oversees Region North (Gwalior, Morena, Jaipur, Ajmer)", "structured_fk", 0.99, ts, 0),
        ("ENT-PER-ANANYA", "enterprise_supply_ops", "Ananya Deshmukh", "Person", None, json.dumps({"role": "Regional Director (Bhopal-Katni)"}), "enterprise_supply_ops.regions", "database_record", "regions:REG-CENTRAL", "Director Ananya Deshmukh oversees Region Central (Bhopal, Katni)", "structured_fk", 0.99, ts, 0),

        # Facilities in the user's cities
        ("ENT-FAC-101", "enterprise_supply_ops", "Gwalior Precision Engineering Plant", "Organization", None, json.dumps({"facility_id": "FAC-GWL", "city": "Gwalior", "budget_usd": 18500000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-GWL", "FAC-GWL | Gwalior Precision Engineering Plant | Gwalior | $18.5M", "structured_fk", 1.0, ts, 0),
        ("ENT-FAC-201", "enterprise_supply_ops", "Morena Solar & Agro-Logistics Hub", "Organization", None, json.dumps({"facility_id": "FAC-MRN", "city": "Morena", "budget_usd": 11200000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-MRN", "FAC-MRN | Morena Solar & Agro-Logistics Hub | Morena | $11.2M", "structured_fk", 1.0, ts, 0),
        ("ENT-FAC-301", "enterprise_supply_ops", "Jaipur Smart Grid & Digital Park", "Organization", None, json.dumps({"facility_id": "FAC-JPR", "city": "Jaipur", "budget_usd": 24000000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-JPR", "FAC-JPR | Jaipur Smart Grid & Digital Park | Jaipur | $24.0M", "structured_fk", 1.0, ts, 0),
        ("ENT-FAC-AJM", "enterprise_supply_ops", "Ajmer Heavy Traction & Forging Unit", "Organization", None, json.dumps({"facility_id": "FAC-AJM", "city": "Ajmer", "budget_usd": 15400000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-AJM", "FAC-AJM | Ajmer Heavy Traction & Forging Unit | Ajmer | $15.4M", "structured_fk", 1.0, ts, 0),
        ("ENT-FAC-401", "enterprise_supply_ops", "Katni Defense & Mineral Ordnance Hub", "Organization", None, json.dumps({"facility_id": "FAC-KTN", "city": "Katni", "budget_usd": 17000000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-KTN", "FAC-KTN | Katni Defense & Mineral Ordnance Hub | Katni | $17.0M", "structured_fk", 1.0, ts, 0),
        ("ENT-FAC-BPL", "enterprise_supply_ops", "Bhopal Bio-Pharma & Electricals Complex", "Organization", None, json.dumps({"facility_id": "FAC-BPL", "city": "Bhopal", "budget_usd": 21800000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-BPL", "FAC-BPL | Bhopal Bio-Pharma & Electricals Complex | Bhopal | $21.8M", "structured_fk", 1.0, ts, 0),
        ("ENT-FAC-AMD", "enterprise_supply_ops", "Ahmedabad Gandhinagar GIFT Tech Tower", "Organization", None, json.dumps({"facility_id": "FAC-AMD", "city": "Ahmedabad / Gandhinagar", "budget_usd": 29500000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-AMD", "FAC-AMD | Ahmedabad Gandhinagar GIFT Tech Tower | $29.5M", "structured_fk", 1.0, ts, 0),
        ("ENT-FAC-MUM", "enterprise_supply_ops", "Mumbai Refinery & Enterprise Core", "Organization", None, json.dumps({"facility_id": "FAC-MUM", "city": "Mumbai", "budget_usd": 36000000}), "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-MUM", "FAC-MUM | Mumbai Refinery & Enterprise Core | Mumbai | $36.0M", "structured_fk", 1.0, ts, 0),

        # The 8 Indian Companies selected by the user (+ 2 alias nodes for Entity Resolution)
        ("ENT-VND-01", "enterprise_supply_ops", "Larsen & Toubro (L&T)", "Organization", None, json.dumps({"vendor_id": "VND-01", "city": "Gwalior", "score": 95.5}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-01", "VND-01 | Larsen & Toubro (L&T) | Gwalior | Heavy Defense & Structural Turbines", "structured_fk", 1.0, ts, 0),
        ("ENT-VND-02", "enterprise_supply_ops", "L&T Engineering Ltd.", "Organization", "ENT-VND-01", json.dumps({"vendor_id": "VND-02", "city": "Gwalior", "score": 95.0}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-02", "VND-02 | L&T Engineering Ltd. | Gwalior | Heavy Defense & Structural Turbines", "structured_fk", 0.92, ts, 0),
        ("ENT-VND-03", "enterprise_supply_ops", "Bharat Forge", "Organization", None, json.dumps({"vendor_id": "VND-03", "city": "Katni", "score": 93.5}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-03", "VND-03 | Bharat Forge | Katni | Artillery Barrels & Forged Crankshafts", "structured_fk", 1.0, ts, 0),
        ("ENT-VND-03-ALIAS", "enterprise_supply_ops", "Bharat Forge Limited", "Organization", "ENT-VND-03", json.dumps({"city": "Katni"}), "DOC-2026-02", "document", "DOC-2026-02", "Bharat Forge (formally Bharat Forge Limited) supplies Artillery Barrels & Forged Crankshafts to Katni.", "pattern_ner", 0.91, ts, 0),
        ("ENT-VND-04", "enterprise_supply_ops", "Adani Green Energy", "Organization", None, json.dumps({"vendor_id": "VND-04", "city": "Morena", "score": 62.5}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-04", "VND-04 | Adani Green Energy | Morena | High-Voltage Solar Inverter Arrays", "structured_fk", 1.0, ts, 0),
        ("ENT-VND-05", "enterprise_supply_ops", "Mahindra & Mahindra", "Organization", None, json.dumps({"vendor_id": "VND-05", "city": "Jaipur"}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-05", "VND-05 | Mahindra & Mahindra | Jaipur | Armored Utility Vehicles & Powertrains", "structured_fk", 1.0, ts, 0),
        ("ENT-VND-06", "enterprise_supply_ops", "Reliance Industries", "Organization", None, json.dumps({"vendor_id": "VND-06", "city": "Mumbai", "score": 97.2}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-06", "VND-06 | Reliance Industries | Mumbai | Specialty Polymers & JioCloud Core", "structured_fk", 1.0, ts, 0),
        ("ENT-VND-07", "enterprise_supply_ops", "Tata Consultancy Services (TCS)", "Organization", None, json.dumps({"vendor_id": "VND-07", "city": "Ahmedabad / Gandhinagar", "score": 98.4}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-07", "VND-07 | Tata Consultancy Services (TCS) | Ahmedabad / Gandhinagar | Smart Grid Digital Twin", "structured_fk", 1.0, ts, 0),
        ("ENT-VND-08", "enterprise_supply_ops", "Infosys", "Organization", None, json.dumps({"vendor_id": "VND-08", "city": "Jaipur", "score": 96.0}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-08", "VND-08 | Infosys | Jaipur | AI Supply Chain Telemetry Suite", "structured_fk", 1.0, ts, 0),
        ("ENT-VND-09", "enterprise_supply_ops", "Biocon", "Organization", None, json.dumps({"vendor_id": "VND-09", "city": "Bhopal", "score": 91.8}), "enterprise_supply_ops.vendors", "database_record", "vendors:VND-09", "VND-09 | Biocon | Bhopal | Recombinant Enzymes & API Cold-Chain", "structured_fk", 1.0, ts, 0),

        # Products & Events
        ("ENT-PRD-TURBINE", "enterprise_supply_ops", "Heavy Defense & Structural Turbines", "Product", None, json.dumps({"category": "Defense Engineering"}), "enterprise_supply_ops.shipments", "database_record", "shipments:SHP-5001", "Component: Heavy Defense & Structural Turbines delivered to Gwalior (FAC-GWL)", "structured_fk", 0.99, ts, 0),
        ("ENT-PRD-MERCURY", "enterprise_supply_ops", "Project Mercury", "Product", None, json.dumps({"category": "Defense Telemetry"}), "DOC-2026-01", "document", "DOC-2026-01", "Gwalior Precision Engineering Plant manufactures Project Mercury defense telemetry.", "pattern_ner", 0.95, ts, 0),
        ("ENT-EVT-INC701", "enterprise_supply_ops", "Transformer Thermal Failure (INC-701)", "Event", None, json.dumps({"severity": "CRITICAL", "city": "Morena", "impact_usd": 1420000}), "enterprise_supply_ops.quality_incidents", "database_record", "quality_incidents:INC-701", "INC-701 | CRITICAL | Transformer Thermal Failure at Morena Sub-Station | $1,420,000", "structured_fk", 1.0, ts, 0),
        ("ENT-DOC-04", "enterprise_supply_ops", "Compliance Directive DOC-2026-04", "Document", None, json.dumps({"doc_id": "DOC-2026-04"}), "DOC-2026-04", "document", "DOC-2026-04", "Emergency Compliance Suspension: Adani Green Energy suspended at Morena Sub-Station 2026-08-20.", "pattern_ner", 1.0, ts, 0),

        # BIRD Demo Entities (Gwalior, Jaipur, Bhopal, Mumbai, Ahmedabad/Gandhinagar)
        ("ENT-SCH-A", "california_schools_bird_demo", "School A (Scindia STEM Academy Gwalior)", "Organization", None, json.dumps({"cds": "01612590130229", "city": "Gwalior", "charter": 1, "sat_math": 642}), "california_schools_bird_demo.schools", "database_record", "schools:01612590130229", "01612590130229 | School A (Scindia STEM Academy Gwalior) | Gwalior | Region North | Math SAT: 642", "structured_fk", 1.0, ts, 0),
        ("ENT-SCH-SV", "california_schools_bird_demo", "Bhopal Regional Science Academy", "Organization", None, json.dumps({"cds": "43696664330585", "city": "Bhopal", "charter": 1, "sat_math": 658}), "california_schools_bird_demo.schools", "database_record", "schools:43696664330585", "43696664330585 | Bhopal Regional Science Academy | Bhopal | Math SAT: 658", "structured_fk", 1.0, ts, 0),
        ("ENT-SCH-TP", "california_schools_bird_demo", "Mumbai Institute of Science Magnet", "Organization", None, json.dumps({"cds": "37683383730017", "city": "Mumbai", "charter": 0, "sat_math": 665}), "california_schools_bird_demo.schools", "database_record", "schools:37683383730017", "37683383730017 | Mumbai Institute of Science Magnet | Mumbai | Math SAT: 665", "structured_fk", 1.0, ts, 0),
        ("ENT-LOC-CA-NORTH", "california_schools_bird_demo", "Region North", "Location", None, json.dumps({"cities": "Gwalior, Jaipur, Ajmer, Morena"}), "california_schools_bird_demo.schools", "database_record", "schools:Region_North", "Region North Educational Corridor (Gwalior, Jaipur, Ajmer, Morena)", "structured_fk", 1.0, ts, 0),
        ("ENT-CON-QUANTUM", "california_schools_bird_demo", "Indian Quantum Curriculum Initiative", "Concept", None, json.dumps({"program_type": "STEM Grant"}), "DOC-EDU-101", "document", "DOC-EDU-101", "School A (Gwalior) partners with Bhopal Regional Science Academy under the Indian Quantum Curriculum Initiative.", "pattern_ner", 0.95, ts, 0),
    ]
    cur.executemany("INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", entities)

    relationships = [
        # Facility -> City & Region Relationships
        ("REL-01", "enterprise_supply_ops", "ENT-FAC-101", "ENT-CITY-GWL", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-GWL", "Gwalior Precision Engineering Plant (FAC-GWL) is located in Gwalior", "structured_fk", 1.0, ts, 0, None),
        ("REL-01B", "enterprise_supply_ops", "ENT-CITY-GWL", "ENT-REG-NORTH", "PART_OF", "enterprise_supply_ops.regions", "database_record", "regions:REG-NORTH", "Gwalior is part of Region North (Gwalior-Morena-Jaipur-Ajmer)", "structured_fk", 1.0, ts, 0, None),
        ("REL-02", "enterprise_supply_ops", "ENT-FAC-101", "ENT-REG-NORTH", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-GWL", "Facility FAC-GWL (Gwalior Precision Engineering Plant) foreign key region_id -> REG-NORTH", "structured_fk", 1.0, ts, 0, None),
        ("REL-03", "enterprise_supply_ops", "ENT-FAC-201", "ENT-CITY-MRN", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-MRN", "Morena Solar & Agro-Logistics Hub (FAC-MRN) is located in Morena", "structured_fk", 1.0, ts, 0, None),
        ("REL-03B", "enterprise_supply_ops", "ENT-FAC-201", "ENT-REG-NORTH", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-MRN", "Facility FAC-MRN (Morena) foreign key region_id -> REG-NORTH", "structured_fk", 1.0, ts, 0, None),
        ("REL-03C", "enterprise_supply_ops", "ENT-CITY-MRN", "ENT-REG-NORTH", "PART_OF", "enterprise_supply_ops.regions", "database_record", "regions:REG-NORTH", "Morena is part of Region North (Gwalior-Morena-Jaipur-Ajmer)", "structured_fk", 1.0, ts, 0, None),
        ("REL-04", "enterprise_supply_ops", "ENT-FAC-301", "ENT-CITY-JPR", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-JPR", "Jaipur Smart Grid & Digital Park (FAC-JPR) is located in Jaipur", "structured_fk", 1.0, ts, 0, None),
        ("REL-04B", "enterprise_supply_ops", "ENT-FAC-301", "ENT-REG-NORTH", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-JPR", "Facility FAC-JPR (Jaipur Smart Grid & Digital Park) foreign key region_id -> REG-NORTH", "structured_fk", 1.0, ts, 0, None),
        ("REL-04C", "enterprise_supply_ops", "ENT-CITY-JPR", "ENT-REG-NORTH", "PART_OF", "enterprise_supply_ops.regions", "database_record", "regions:REG-NORTH", "Jaipur is part of Region North (Gwalior-Morena-Jaipur-Ajmer)", "structured_fk", 1.0, ts, 0, None),
        ("REL-04D", "enterprise_supply_ops", "ENT-CITY-AJM", "ENT-REG-NORTH", "PART_OF", "enterprise_supply_ops.regions", "database_record", "regions:REG-NORTH", "Ajmer is part of Region North (Gwalior-Morena-Jaipur-Ajmer)", "structured_fk", 1.0, ts, 0, None),
        ("REL-04E", "enterprise_supply_ops", "ENT-FAC-AJM", "ENT-CITY-AJM", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-AJM", "Ajmer Heavy Traction & Forging Unit (FAC-AJM) is located in Ajmer", "structured_fk", 1.0, ts, 0, None),
        ("REL-04F", "enterprise_supply_ops", "ENT-FAC-AJM", "ENT-REG-NORTH", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-AJM", "Facility FAC-AJM (Ajmer Heavy Traction & Forging Unit) foreign key region_id -> REG-NORTH", "structured_fk", 1.0, ts, 0, None),
        ("REL-05", "enterprise_supply_ops", "ENT-FAC-401", "ENT-CITY-KTN", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-KTN", "Katni Defense & Mineral Ordnance Hub (FAC-KTN) is located in Katni", "structured_fk", 1.0, ts, 0, None),
        ("REL-05B", "enterprise_supply_ops", "ENT-FAC-401", "ENT-REG-CENTRAL", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-KTN", "Facility FAC-KTN (Katni) foreign key region_id -> REG-CENTRAL", "structured_fk", 1.0, ts, 0, None),
        ("REL-05C", "enterprise_supply_ops", "ENT-CITY-KTN", "ENT-REG-CENTRAL", "PART_OF", "enterprise_supply_ops.regions", "database_record", "regions:REG-CENTRAL", "Katni is part of Region Central (Bhopal-Katni)", "structured_fk", 1.0, ts, 0, None),
        ("REL-06", "enterprise_supply_ops", "ENT-FAC-BPL", "ENT-CITY-BPL", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-BPL", "Bhopal Bio-Pharma & Electricals Complex (FAC-BPL) is located in Bhopal", "structured_fk", 1.0, ts, 0, None),
        ("REL-06B", "enterprise_supply_ops", "ENT-FAC-BPL", "ENT-REG-CENTRAL", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-BPL", "Facility FAC-BPL (Bhopal Bio-Pharma & Electricals Complex) foreign key region_id -> REG-CENTRAL", "structured_fk", 1.0, ts, 0, None),
        ("REL-06C", "enterprise_supply_ops", "ENT-CITY-BPL", "ENT-REG-CENTRAL", "PART_OF", "enterprise_supply_ops.regions", "database_record", "regions:REG-CENTRAL", "Bhopal is part of Region Central (Bhopal-Katni)", "structured_fk", 1.0, ts, 0, None),
        ("REL-07", "enterprise_supply_ops", "ENT-FAC-AMD", "ENT-REG-GUJ", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-AMD", "Ahmedabad Gandhinagar GIFT Tech Tower (FAC-AMD) is located in Ahmedabad / Gandhinagar", "structured_fk", 1.0, ts, 0, None),
        ("REL-08", "enterprise_supply_ops", "ENT-FAC-MUM", "ENT-REG-MUM", "LOCATED_IN", "enterprise_supply_ops.facilities", "database_record", "facilities:FAC-MUM", "Mumbai Refinery & Enterprise Core (FAC-MUM) is located in Mumbai", "structured_fk", 1.0, ts, 0, None),

        # Indian Companies -> Facilities Supply Links
        ("REL-09", "enterprise_supply_ops", "ENT-VND-01", "ENT-FAC-101", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-901", "Contract CNT-901 links Larsen & Toubro (L&T) (VND-01) to Gwalior Precision Engineering Plant ($6.4M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-10", "enterprise_supply_ops", "ENT-VND-02", "ENT-CITY-AJM", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-902", "Contract CNT-902 links L&T Engineering Ltd. (VND-02) to Ajmer Heavy Traction Unit ($2.85M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-11", "enterprise_supply_ops", "ENT-VND-03", "ENT-FAC-401", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-903", "Contract CNT-903 links Bharat Forge (VND-03) to Katni Defense & Mineral Ordnance Hub ($8.9M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-12", "enterprise_supply_ops", "ENT-VND-04", "ENT-FAC-201", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-904", "Contract CNT-904 links Adani Green Energy (VND-04) to Morena Solar & Agro-Logistics Hub ($5.4M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-13", "enterprise_supply_ops", "ENT-VND-05", "ENT-FAC-301", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-905", "Contract CNT-905 links Mahindra & Mahindra (VND-05) to Jaipur Smart Grid & Digital Park ($4.1M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-14", "enterprise_supply_ops", "ENT-VND-06", "ENT-FAC-MUM", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-906", "Contract CNT-906 links Reliance Industries (VND-06) to Mumbai Refinery & Enterprise Core ($12.5M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-15", "enterprise_supply_ops", "ENT-VND-07", "ENT-FAC-AMD", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-907", "Contract CNT-907 links Tata Consultancy Services (TCS) (VND-07) to Ahmedabad Gandhinagar GIFT Tech Tower ($9.2M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-16", "enterprise_supply_ops", "ENT-VND-08", "ENT-FAC-301", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-908", "Contract CNT-908 links Infosys (VND-08) to Jaipur Smart Grid & Digital Park ($5.75M)", "structured_fk", 1.0, ts, 0, None),
        ("REL-17", "enterprise_supply_ops", "ENT-VND-09", "ENT-FAC-BPL", "SUPPLIES_TO", "enterprise_supply_ops.procurement_contracts", "database_record", "procurement_contracts:CNT-909", "Contract CNT-909 links Biocon (VND-09) to Bhopal Bio-Pharma & Electricals Complex ($4.95M)", "structured_fk", 1.0, ts, 0, None),

        ("REL-18", "enterprise_supply_ops", "ENT-FAC-101", "ENT-PRD-MERCURY", "OWNS", "DOC-2026-01", "document", "DOC-2026-01", "Gwalior Precision Engineering Plant manufactures Project Mercury defense telemetry.", "pattern_ner", 0.96, ts, 0, None),
        ("REL-19", "enterprise_supply_ops", "ENT-EVT-INC701", "ENT-VND-04", "CAUSED_BY", "enterprise_supply_ops.quality_incidents", "database_record", "quality_incidents:INC-701", "Incident INC-701 (Transformer Thermal Failure at Morena) attributed to Adani Green Energy (VND-04)", "structured_fk", 1.0, ts, 0, None),
        ("REL-20", "enterprise_supply_ops", "ENT-DOC-04", "ENT-VND-04", "REFERENCES", "DOC-2026-04", "document", "DOC-2026-04", "Directive DOC-2026-04 suspends Adani Green Energy (VND-04) at Morena Sub-Station effective 2026-08-20.", "pattern_ner", 1.0, ts, 0, None),
        ("REL-21", "enterprise_supply_ops", "ENT-PER-ELENA", "ENT-REG-NORTH", "MANAGES", "enterprise_supply_ops.regions", "database_record", "regions:REG-NORTH", "Rajeshwar Scindia is Regional Director for Region North (Gwalior, Morena, Jaipur, Ajmer)", "structured_fk", 1.0, ts, 0, None),
        ("REL-22", "enterprise_supply_ops", "ENT-PER-ANANYA", "ENT-REG-CENTRAL", "MANAGES", "enterprise_supply_ops.regions", "database_record", "regions:REG-CENTRAL", "Ananya Deshmukh is Regional Director for Region Central (Bhopal, Katni)", "structured_fk", 1.0, ts, 0, None),

        # Inferred Transitive Relationships (is_inferred = 1)
        ("REL-INF-01", "enterprise_supply_ops", "ENT-VND-01", "ENT-REG-NORTH", "CONNECTED_TO", "inferred_graph_rule", "inferred_rule", "rule:vendor_facility_region_transitivity", "Inferred via transitive path: Larsen & Toubro (L&T) -> SUPPLIES_TO -> Gwalior Precision Engineering Plant -> LOCATED_IN -> Region North", "transitive_inference", 0.84, ts, 1, "Vendor(X) SUPPLIES_TO Facility(Y) AND Facility(Y) LOCATED_IN Region(Z) => Vendor(X) CONNECTED_TO Region(Z)"),
        ("REL-INF-02", "enterprise_supply_ops", "ENT-VND-04", "ENT-REG-NORTH", "CONNECTED_TO", "inferred_graph_rule", "inferred_rule", "rule:vendor_facility_region_transitivity", "Inferred via transitive path: Adani Green Energy -> SUPPLIES_TO -> Morena Solar & Agro-Logistics Hub -> LOCATED_IN -> Region North", "transitive_inference", 0.80, ts, 1, "Vendor(X) SUPPLIES_TO Facility(Y) AND Facility(Y) LOCATED_IN Region(Z) => Vendor(X) CONNECTED_TO Region(Z)"),

        # BIRD Demo Relationships
        ("REL-EDU-01", "california_schools_bird_demo", "ENT-SCH-A", "ENT-LOC-CA-NORTH", "LOCATED_IN", "california_schools_bird_demo.schools", "database_record", "schools:01612590130229", "School A (Scindia STEM Academy Gwalior) record has City = 'Gwalior', Region = 'Region North'", "structured_fk", 1.0, ts, 0, None),
        ("REL-EDU-02", "california_schools_bird_demo", "ENT-SCH-A", "ENT-CON-QUANTUM", "PART_OF", "DOC-EDU-101", "document", "DOC-EDU-101", "School A (Gwalior) partners with Bhopal Regional Science Academy under the Indian Quantum Curriculum Initiative.", "pattern_ner", 0.95, ts, 0, None),
        ("REL-EDU-03", "california_schools_bird_demo", "ENT-SCH-SV", "ENT-CON-QUANTUM", "PART_OF", "DOC-EDU-101", "document", "DOC-EDU-101", "Bhopal Regional Science Academy is a partner in the Indian Quantum Curriculum Initiative.", "pattern_ner", 0.95, ts, 0, None),
        ("REL-EDU-INF-01", "california_schools_bird_demo", "ENT-SCH-A", "ENT-SCH-SV", "CONNECTED_TO", "inferred_graph_rule", "inferred_rule", "rule:shared_program_partnership", "Inferred partnership: Both School A (Gwalior) and Bhopal Regional Science Academy are PART_OF Indian Quantum Curriculum Initiative", "transitive_inference", 0.86, ts, 1, "Org(A) PART_OF Program(P) AND Org(B) PART_OF Program(P) => Org(A) CONNECTED_TO Org(B)"),
    ]
    cur.executemany("INSERT INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", relationships)

    resolutions = [
        (
            "RES-01",
            "ENT-VND-02",
            "ENT-VND-01",
            0.94,
            "High lexical & attribute similarity ('L&T Engineering Ltd.' vs 'Larsen & Toubro (L&T)'), identical city (Gwalior) and product ('Heavy Defense & Structural Turbines'), corroborated by audit memo DOC-2026-01.",
            json.dumps([
                "vendors:VND-01 (Larsen & Toubro (L&T)) & vendors:VND-02 (L&T Engineering Ltd.) share product 'Heavy Defense & Structural Turbines'",
                "DOC-2026-01 explicitly states: 'Larsen & Toubro (L&T) (also registered in legacy ERP as L&T Engineering Ltd.)'",
            ]),
            "SUGGESTED",
            ts,
        ),
        (
            "RES-02",
            "ENT-VND-03-ALIAS",
            "ENT-VND-03",
            0.92,
            "Alias match ('Bharat Forge Limited' vs 'Bharat Forge') extracted from DOC-2026-02 and linked to Katni Artillery Barrels & Forged Crankshafts supplier.",
            json.dumps([
                "vendors:VND-03 lists 'Bharat Forge' in Katni supplying 'Artillery Barrels & Forged Crankshafts'",
                "DOC-2026-02 states: 'Bharat Forge (formally Bharat Forge Limited)'",
            ]),
            "SUGGESTED",
            ts,
        ),
    ]
    cur.executemany("INSERT INTO entity_resolutions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", resolutions)

    conn.commit()
    conn.close()


def add_custom_company_record(
    company_name: str,
    city: str,
    primary_product: str,
    tier_level: int = 1,
    compliance_score: float = 95.0,
    contract_value_usd: float = 5000000.0,
    contract_status: str = "ACTIVE",
    facility_id: str = "FAC-GWL",
) -> Dict[str, Any]:
    """
    User-driven interactive data builder:
    Inserts a new Indian company, procurement contract, and Knowledge Graph nodes/edges
    into enterprise_supply_ops.db and graph_store.db.
    """
    ensure_sample_databases()
    ts = datetime.now(timezone.utc).isoformat()
    short_hash = hashlib.md5(f"{company_name}:{city}:{ts}".encode()).hexdigest()[:5].upper()
    vendor_id = f"VND-{short_hash}"
    contract_id = f"CNT-{short_hash}"
    ent_id = f"ENT-{short_hash}"

    # 1. Insert into enterprise_supply_ops.db
    db_path = get_db_path("enterprise_supply_ops")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check target facility exists
    fac_row = cur.execute("SELECT * FROM facilities WHERE facility_id = ?", (facility_id,)).fetchone()
    if not fac_row:
        fac_row = cur.execute("SELECT * FROM facilities LIMIT 1").fetchone()
        facility_id = fac_row["facility_id"]
    fac_name = fac_row["facility_name"]
    fac_region_id = fac_row["region_id"]

    cur.execute(
        "INSERT INTO vendors VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            vendor_id,
            company_name,
            f"{city}, India",
            tier_level,
            compliance_score,
            f"contact@{company_name.lower().replace(' ', '')[:10]}.in",
            primary_product,
        ),
    )
    cur.execute(
        "INSERT INTO procurement_contracts VALUES (?, ?, ?, ?, ?, ?)",
        (
            contract_id,
            vendor_id,
            facility_id,
            contract_value_usd,
            contract_status,
            ts[:10],
        ),
    )
    conn.commit()
    conn.close()

    # 2. Insert into Knowledge Graph (graph_store.db)
    gconn = sqlite3.connect(str(get_graph_db_path()))
    gconn.row_factory = sqlite3.Row
    gcur = gconn.cursor()

    excerpt = f"{vendor_id} | {company_name} ({city}) | Product: {primary_product} | Contract {contract_id}: ${contract_value_usd:,.0f} ({contract_status})"
    gcur.execute(
        "INSERT INTO entities VALUES (?, 'enterprise_supply_ops', ?, 'Organization', NULL, ?, 'enterprise_supply_ops.vendors', 'database_record', ?, ?, 'user_data_studio', 1.0, ?, 0)",
        (
            ent_id,
            company_name,
            json.dumps({"vendor_id": vendor_id, "city": city, "product": primary_product, "score": compliance_score}),
            f"vendors:{vendor_id}",
            excerpt,
            ts,
        ),
    )

    # Link to City node if present, else create city node
    city_row = gcur.execute(
        "SELECT id, name FROM entities WHERE LOWER(name) = LOWER(?) AND entity_type = 'Location'",
        (city.strip(),),
    ).fetchone()
    if city_row:
        city_ent_id = city_row["id"]
    else:
        city_ent_id = f"ENT-CITY-{short_hash}"
        gcur.execute(
            "INSERT INTO entities VALUES (?, 'enterprise_supply_ops', ?, 'Location', NULL, ?, 'user_data_studio', 'database_record', ?, ?, 'user_data_studio', 1.0, ?, 0)",
            (
                city_ent_id,
                city.strip(),
                json.dumps({"country": "India"}),
                f"location:{city.strip()}",
                f"Indian city hub {city.strip()} added via Data Studio",
                ts,
            ),
        )
        region_ent_map = {
            "REG-NORTH": "ENT-REG-NORTH",
            "REG-CENTRAL": "ENT-REG-CENTRAL",
            "REG-GUJ": "ENT-REG-GUJ",
            "REG-WEST-GUJ": "ENT-REG-GUJ",
            "REG-MUM": "ENT-REG-MUM",
            "REG-WEST-MAH": "ENT-REG-MUM",
        }
        reg_ent_id = region_ent_map.get(fac_region_id, "ENT-REG-NORTH")
        if reg_ent_id != city_ent_id:
            rel_reg_id = f"REL-REG-{short_hash}"
            gcur.execute(
                "INSERT INTO relationships VALUES (?, 'enterprise_supply_ops', ?, ?, 'PART_OF', 'user_data_studio', 'database_record', ?, ?, 'user_data_studio', 1.0, ?, 0, NULL)",
                (
                    rel_reg_id,
                    city_ent_id,
                    reg_ent_id,
                    f"regions:{fac_region_id}",
                    f"City hub {city.strip()} is part of regional corridor {fac_region_id}",
                    ts,
                ),
            )

    rel_loc_id = f"REL-LOC-{short_hash}"
    gcur.execute(
        "INSERT INTO relationships VALUES (?, 'enterprise_supply_ops', ?, ?, 'LOCATED_IN', 'enterprise_supply_ops.vendors', 'database_record', ?, ?, 'user_data_studio', 1.0, ?, 0, NULL)",
        (
            rel_loc_id,
            ent_id,
            city_ent_id,
            f"vendors:{vendor_id}",
            f"{company_name} is headquartered / operating in {city.strip()}",
            ts,
        ),
    )

    # Also link to Facility entity if present in graph
    fac_ent = gcur.execute(
        "SELECT id FROM entities WHERE LOWER(name) = LOWER(?)",
        (fac_name,),
    ).fetchone()
    if fac_ent:
        rel_sup_id = f"REL-SUP-{short_hash}"
        gcur.execute(
            "INSERT INTO relationships VALUES (?, 'enterprise_supply_ops', ?, ?, 'SUPPLIES_TO', 'enterprise_supply_ops.procurement_contracts', 'database_record', ?, ?, 'user_data_studio', 1.0, ?, 0, NULL)",
            (
                rel_sup_id,
                ent_id,
                fac_ent["id"],
                f"procurement_contracts:{contract_id}",
                f"Contract {contract_id} links {company_name} to {fac_name} (${contract_value_usd:,.0f})",
                ts,
            ),
        )

    gconn.commit()
    gconn.close()

    return {
        "status": "created",
        "vendor_id": vendor_id,
        "vendor_name": company_name,
        "contract_id": contract_id,
        "entity_id": ent_id,
        "company_name": company_name,
        "city": city,
        "facility_name": fac_name,
        "primary_product": primary_product,
        "contract_value_usd": contract_value_usd,
    }


def add_custom_graph_relationship(
    source_entity_id: str,
    target_entity_id: str,
    rel_type: str,
    excerpt: str,
    is_inferred: bool = False,
) -> Dict[str, Any]:
    ensure_sample_databases()
    ts = datetime.now(timezone.utc).isoformat()
    short_hash = hashlib.md5(f"{source_entity_id}:{rel_type}:{target_entity_id}:{ts}".encode()).hexdigest()[:6].upper()
    rel_id = f"REL-USR-{short_hash}"

    gconn = sqlite3.connect(str(get_graph_db_path()))
    gcur = gconn.cursor()
    gcur.execute(
        "INSERT INTO relationships VALUES (?, 'enterprise_supply_ops', ?, ?, ?, 'user_data_studio', 'database_record', ?, ?, 'user_data_studio', 1.0, ?, ?, ?)",
        (
            rel_id,
            source_entity_id,
            target_entity_id,
            rel_type,
            f"user_edge:{rel_id}",
            excerpt or f"User-defined relationship {rel_type}",
            ts,
            1 if is_inferred else 0,
            "User-specified inference rule" if is_inferred else None,
        ),
    )
    gconn.commit()
    gconn.close()
    return {"status": "created", "relationship_id": rel_id}
