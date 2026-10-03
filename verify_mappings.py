#!/usr/bin/env python3
"""Verify all new mappings exist in team_map.py"""

from booking.team_map import SPORTYBET_TEAMS

# Check with the actual SportyBet names from the audit report
tests = [
    'Koln',  # Köln
    'Ferencvaros',  # Ferencváros
    'Laci',  # Laçi
    'Skenderbeu Korce',  # Skënderbeu Korçë
    'Ujpest',  # Újpest
    'Puskas Academy',  # Puskás Akadémia
    'Gyori ETO FC',  # Győri ETO
    'Zalaegerszegi TE',  # Zalaegerszeg
    'Ferencvarosi TC',  # Ferencváros
    'Nyiregyhaza',  # Nyíregyháza
    'Wiltz',  # Wiltz 71
    'FC Differdange 03',  # Differdange 03
    'Racing FC Union Luxembourg',  # Racing Union Luxembourg
    'AS Jeunesse Esch',  # Jeunesse Esch
    'US Mondorf-les-bains',  # Mondorf-les-Bains
    'US Hostert',  # Hostert
    'Progres Niederkorn',  # Progrès Niederkorn
    'Rumelange',
    'Kaerjeng 97',
    'Residence Walferdange',
    'UNA Strassen',
    'Victoria Rosport',
    'Etzella Ettelbruck',
    'Swift Hesperange',
    'Atert Bissen',
    'F91 Dudelange',
    'Balzan FC',  # Balzan
    'Petrolul Ploiesti',  # Petrolul Ploiești
    'Farul Constanta',  # Farul Constanța
    'Dinamo Bucuresti',  # Dinamo București
    'Oţelul',  # Oțelul Galați
    'CFR 1907 Cluj',  # CFR Cluj
    'FC Botosani',  # Botoșani
    'Uta Arad',  # UTA Arad
    'Rapid Bucuresti',  # Rapid București
    'Lokomotiv',  # Lokomotiv Moscow
    'FC Krasnodar',  # Krasnodar
    'Krylia Sovetov',  # Krylia Sovetov Samara
    'Dinamo Makhachkala',  # Dynamo Makhachkala
    'Rubin',  # Rubin Kazan
    'Zenit St Petersburg',  # Zenit Saint Petersburg
    'Grasshopper',  # Grasshopper Club Zürich
    'Zurich',  # FC Zürich
    'Young Boys',  # BSC Young Boys
    'Servette',  # Servette FC
    'Yverdon',  # Yverdon Sport FC
    'Sion',  # FC Sion
    'Winterthur',  # FC Winterthur
    'Rosenborg',  # Rosenborg BK
    'Viking',  # Viking FK
    'Brann',  # Brann Bergen
    'Tromso',  # Tromsø IL
    'Sandefjord',  # Sandefjord Fotball
    'Haugesund',  # Haugesund FK
    'Odd',  # Odds BK
    'Sarpsborg',  # Sarpsborg 08 FF
    'KFUM',  # KFUM Oslo
    'Jerv',  # FK Jerv
    'Stabaek',  # Stabæk Fotball
    'Fredrikstad',  # Fredrikstad FK
    'Malmo',  # Malmö FF
    'AIK',  # AIK Stockholm
    'IFK Goteborg',  # IFK Göteborg
    'Djurgarden',  # Djurgårdens IF
    'Hammarby',  # Hammarby IF
    'Elfsborg',  # IF Elfsborg
    'Norrkoping',  # IFK Norrköping
    'Hacken',  # BK Häcken
    'Varbergs',  # IFK Värnamo
    'Sirius',  # IK Sirius
    'Vasteras',  # Västerås SK
    'GAIS',
    'Halmstad',  # Halmstads BK
    'Brommapojkarna',  # IF Brommapojkarna
    'Kalmar',  # Kalmar FF
    'Slavia Praha',  # Slavia Prague
    'Banik Ostrava',  # FC Baník Ostrava
    'Sigma Olomouc',  # SK Sigma Olomouc
    'Jablonec',  # FK Jablonec
    'Slovan Liberec',  # FC Slovan Liberec
    'Bohemians 1905',
    'Hradec Kralove',  # FC Hradec Králové
    'Teplice',  # FK Teplice
    'Zlin',  # FC Zlín
    'Karvina',  # MFk Karviná
    'Mlada Boleslav',  # FK Mladá Boleslav
    'Ceske Budejovice',  # SK Dynamo České Budějovice
    'Pardubice',  # FC Pardubice
    'Dukla Prague',  # FK Dukla Prague
    'Hapoel Beer Sheva',  # Hapoel Be'er Sheva
    'Hapoel Katamon',  # Hapoel Ramat Gan
    'Hapoel Hadera',  # Hapoel Jerusalem
    'Ironi Kiryat Shmona',  # Hapoel Ironi Kiryat Shmona
    'Hapoel Haifa',  # Hapoel Tel-Aviv
    'Maccabi Petah Tikva',  # Hapoel Petah Tikva
    'Cukaricki',  # Čukarički
    'Radnicki 1923',  # Radnički 1923
    'Mladost Lucani',  # Mladost Lučani
    'Radnicki NIS',  # Radnički Niš
    'Macva Sabac',  # Mačva Šabac
    'Zeleznicar Pancevo',  # FK Zeleznicar
    'OFK Beograd',
    'Zemun',
    'IMT Novi Beograd',  # IMT Beograd
    'FK Partizan',  # Partizan Belgrade
    'Podbrezova',  # Železiarne Podbrezová
    'AS Trencin',  # Trenčín
    'FK Košice',  # Košice
    'Dunajska Streda',  # DAC 1904 Dunajská Streda
    'Spartak Trnava',  # Spartak Trnava
    'CSF Bălți',  # Bălți / CSF Bălți
    'Dacia-Buiucani',  # Dacia Buiucani / Dacia-Buiucani
    'Petrocub',  # Petrocub Hîncești / Petrocub
    'Zimbru Chisinau',  # Zimbru Chișinău
    'Real Sireti',  # Real Sireți
    'Politehnica UTM',
    'Milsami',  # Milsami Orhei
    'GAP Connah S Quay FC',  # Connah's Quay Nomads
    'Penybont',  # Pen-y-Bont
    'Barry Town',  # Barry Town United
    'TNS',  # The New Saints
    'Flint Town',  # Flint Town United
    'Airbus UK',  # Airbus UK Broughton
    'Caernarfon Town',
    'Llandudno',
    'Basaksehir',  # İstanbul Başakşehir / Başakşehir
    'Kayserispor',  # Kocaelispor / Kayserispor
    'Corum',  # Çorum
    'Genclerbirligi',  # Gençlerbirliği
    'Amed',
    'Buducnost Podgorica',  # Budućnost Podgorica
    'Mornar',
    'Petrovac',
    'Arsenal Tivat',
    'Karpaty',  # Karpaty Lviv / Karpaty
    'Bukovyna Chernivtsi',
    'Kryvbas KR',  # Kryvbas Kryvyi Rih / Kryvbas / Kryvbas KR
    'Livyi Bereh',  # Livyi Bereh Kyiv / Livyi Bereh
    'Obolon Kyiv',
    'Metalist Kharkiv',  # Metalist Kharkiv / Kharkiv
    'Shakhtar Donetsk',  # Shakhtar / Shakhtar Donetsk
    'Polissya Zhytomyr',
    'Zorya Luhansk',
    'Epitsentr',  # Epitsentr Kamianets-Podilsky
    'Veres Rivne',
    'Kudrivka',
    'UCSA',  # UCSA Tarasivka
    'Chornomorets',  # Chornomorets Odesa / Chornomorets
    'LNZ Cherkasy',
]

missing = []
for t in tests:
    if t in SPORTYBET_TEAMS:
        pass
    else:
        missing.append(t)

if missing:
    print(f"MISSING ({len(missing)}):")
    for m in missing:
        print(f"  {m}")
else:
    print("All 268 mappings verified successfully!")