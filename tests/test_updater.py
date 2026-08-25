import updater


def test_unwraps_current_house_info_envelope():
    payload = {"info": {"porchCount": 4}, "sourceType": "GIS_GKH"}
    assert updater._unwrap_house_info(payload) == {"porchCount": 4}


def test_unwrap_returns_none_for_empty_envelope():
    assert updater._unwrap_house_info({"info": None}) is None


def test_extracts_overhaul_fund_from_current_payload():
    payload = {
        "overhaulFundForming": {
            "actual": True,
            "code": "4",
            "overhaulFundFormingMethod": "Счет регионального оператора",
            "majorRepairsFormingMethod": "Формирование фонда капитального ремонта",
        }
    }

    characteristics = updater._extract_characteristics("house-1", payload)
    funds = updater._extract_overhaul_funds("house-1", payload)

    assert characteristics["overhaul_fund_forming_code"] == "4"
    assert characteristics["overhaul_fund_forming_name"] == "Счет регионального оператора"
    assert funds == [
        {
            "gis_guid": "house-1",
            "fund_forming_code": "4",
            "fund_forming_name": "Счет регионального оператора",
            "fund_attribute_code": None,
            "fund_attribute_name": None,
            "fund_attribute_tag": None,
            "status": "active",
            "start_date": None,
            "end_date": None,
            "overhaul_fund_forming_method": "Счет регионального оператора",
        }
    ]


def test_energy_efficiency_designation_is_not_stored_as_code():
    payload = {
        "energyEfficiency": {
            "energyEfficiencyDesignation": "Не установлено",
        }
    }

    characteristics = updater._extract_characteristics("house-1", payload)

    assert characteristics["energy_efficiency_code"] is None
    assert characteristics["energy_efficiency_name"] == "Не установлено"
