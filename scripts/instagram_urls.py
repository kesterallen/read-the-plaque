
import requests

#(other side of sardine point) https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xat1/t51.2885-15/e15/11351792_1208044585888120_1369859406_n.jpg
#(other side of John Pittman) https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/10508056_1468043440159365_1696685853_n.jpg
#(other side of Old Douglas) https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/11251944_748077551969815_157026683_n.jpg
#(other side of Buddah) https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10899002_830966723611429_1773165254_n.jpg' ],

img_urls = [
    #['Nicolas Provot', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xta1/t51.2885-15/sh0.08/e35/12394046_229071250757522_899705679_n.jpg' ],
    ['Reverend John Dubree', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xta1/t51.2885-15/sh0.08/e35/12230912_904961272905772_174486404_n.jpg' ],
    ['Bonnie and Clyde', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/sh0.08/e35/12224072_1724738454424648_443607577_n.jpg' ],
    ['The First Courthose for the County of Hempstead', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpf1/t51.2885-15/sh0.08/e35/12299033_931886633543256_1711721514_n.jpg' ],
    ['Royston Factory Mill', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/sh0.08/e35/12292696_1666126166965075_1013358080_n.jpg' ],
    ['Morrisonville', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/11918005_1481313945526114_1531433320_n.jpg' ],
    ['Sardine Point The Cut Off', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfp1/t51.2885-15/e15/11351729_447523358789568_1003771095_n.jpg' ],
    ['Marsalis Mansion Motel', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/11348180_1661011060812756_941665441_n.jpg' ],
    ['Ancient Mounds Trail: Poverty Point Earthworks', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xat1/t51.2885-15/e15/11374547_901914546541031_188350074_n.jpg' ],
    ['Earthworks of Poverty Point', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xap1/t51.2885-15/e15/11419258_1606352672973342_1033649653_n.jpg' ],
    ['Johnny Winter', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/11375776_949192708435771_1059849986_n.jpg' ],
    ['James "Son" Thomas', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/11249277_524331031051360_1732788428_n.jpg' ],
    ['Birthplace of Kermit the Frog', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/11378978_857570600999998_618474727_n.jpg' ],
    ["Muddy Waters's House", 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xat1/t51.2885-15/e15/11429776_1444768202499248_1602626570_n.jpg' ],
    ['WROX Radio', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/11327100_1668526643366669_759717797_n.jpg' ],
    ['Wade Walton', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/11313366_432026303652359_979006843_n.jpg' ],
    ['W. C. Handy', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/1172226_488830944614834_80387236_n.jpg' ],
    ['Hopson Plantation', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xft1/t51.2885-15/e15/11243531_471360326377332_1254299366_n.jpg' ],
    ['The Peavine', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xap1/t51.2885-15/e15/11264734_886305068110221_1037568057_n.jpg' ],
    ['Sgt. John A. Pittman, Medal of Honor', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/11380167_438627526297826_2059483096_n.jpg' ],
    ['Robert L. Johnson', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/11376416_449926105169241_1409572048_n.jpg' ],
    ['Robert Johnson', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/11325003_385689854964220_1576852053_n.jpg' ],
    ['Bobbie Gentry', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/11266642_399927716872855_1821602053_n.jpg' ],
    ["Greenwood's First Aresian Well", 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/11247671_1022638341102453_176487142_n.jpg' ],
    ['Greenwood Underpass', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/10724175_1873421519550009_835819151_n.jpg' ],
    ['B. B. King Birthplace', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/11424689_900422446661541_1719520685_n.jpg' ],
    ['Holmes County Blues Tchula', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xap1/t51.2885-15/e15/11410416_1667960906750107_495576780_n.jpg' ],
    ['Gatemouth Moore', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xft1/t51.2885-15/e15/1741714_141780252821201_213077443_n.jpg' ],
    ['Old Douglas', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfp1/t51.2885-15/e15/11375762_1646497428897495_757649359_n.jpg' ],
    ['Yokena Presbyterian Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/10296922_1012199558803919_816700150_n.jpg' ],
    ['Chamberlain - Hunt Academy', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfp1/t51.2885-15/e15/11247926_1642174052691837_1952328016_n.jpg' ],
    ["Coleman's Crossroads", 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/11325068_1092147787480190_2055508894_n.jpg' ],
    ['Bethel Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xft1/t51.2885-15/e15/11424689_922393967820570_1722457685_n.jpg' ],
    ['Gloster', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xap1/t51.2885-15/e15/10949045_122670054738092_2138116111_n.jpg' ],
    ['City of Eunice', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/1963184_492320717600316_2030269524_n.jpg' ],
    ['In Memory of James (Slim Harpo) Moore', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfp1/t51.2885-15/e15/11372402_1587629024846562_1416355941_n.jpg' ],
    ['James "Slim Harpo" Moore', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/11376337_1603812313234836_430021423_n.jpg' ],
    ['Port Barre', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xap1/t51.2885-15/e15/11330744_1023515307658748_981051710_n.jpg' ],
    ['City of Thibodaux', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/11281976_353385584868042_1782119127_n.jpg' ],
    ["Loge L'Humble Chaumiere", 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtp1/t51.2885-15/e15/11195836_430656073762524_1893749469_n.jpg' ],
    ['La Place des Creoles', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xat1/t51.2885-15/e15/11205734_295785930545676_1236987022_n.jpg' ],
    ['Southern University', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/11142917_1054784077869071_14302264_n.jpg' ],
    ['West Feliciana Railroad', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/11143002_455740021242916_2035274195_n.jpg' ],
    ['Bayou Sara', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xta1/t51.2885-15/e15/11116989_972110186141799_1064321030_n.jpg' ],
    ['Grace Episcopal Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/11111344_462584580560689_1574851046_n.jpg' ],
    ['Livonia Mounds', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtp1/t51.2885-15/e15/11123781_1591556314462236_18843608_n.jpg' ],
    ["Fred's Lounge", 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/10268843_368271046712450_361270235_n.jpg' ],
    ['Acadia Baptist Academy', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/11085195_1631810207052374_2143965834_n.jpg' ],
    ['Academy of the Sacred Heart', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xft1/t51.2885-15/e15/10956791_447224008773757_682484978_n.jpg' ],
    ['Grand Coteau', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/11137683_464812207001220_1561183205_n.jpg' ],
    ['Lake Pontchartrain', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/10919588_1623674421179982_370230270_n.jpg' ],
    ['Fort St. John', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/10956719_775988619163609_531243519_n.jpg' ],
    ['Dr. Lord Beaconsfield Landry', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/11049312_1381898928800704_1602886174_n.jpg' ],
    ['Emmanuel Baptist Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/10995136_762378947194159_1420741217_n.jpg' ],
    ['St. Landry Catholic Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/1515164_1609251955965257_2120040505_n.jpg' ],
    ['Opelousas Colored School', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/11085134_1418513985117558_57121103_n.jpg' ],
    ['Confederate Mass Grave', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/10979619_1721007098125802_654847094_n.jpg' ],
    ['Louisiana Memorial United Methodist Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xap1/t51.2885-15/e15/11008048_686264924830315_212633648_n.jpg' ],
    ['Battle of Lafourche Crossing', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xat1/t51.2885-15/e15/11008348_637773509662648_1469133655_n.jpg' ],
    ['St. Charles Borromeo Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/10979689_350942611764465_983435424_n.jpg' ],
    ['Crowley', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/1971505_1517661301791999_1319139466_n.jpg' ],
    ['Senator John F. Kennedy Presidential Campaign Speech', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/10979706_1547567315526582_1959364159_n.jpg' ],
    ['This Buddha Was Biult for the Shonfa Temple', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10852572_426840190796517_1087813815_n.jpg' ],
    ['First Rock Salt Mine', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10881912_822982377744100_1724294157_n.jpg' ],
    ['Girod House', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/10895036_585008131630105_1446256635_n.jpg' ],
    ['Servant of God', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xft1/t51.2885-15/e15/891516_1546797672229455_2113339361_n.jpg' ],
    ['Washington Artillery Park', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/10899372_1519331128326781_119608291_n.jpg' ],
    ['New Orleans', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-frc/t51.2885-15/e15/10903543_338095269712026_1613871289_n.jpg' ],
    ['The French Market', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/10844113_387539844747969_710909885_n.jpg' ],
    ['Fort St. Charles', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10864877_410504695765934_1163828093_n.jpg' ],
    ['Centerville, Louisiana', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtp1/t51.2885-15/e15/10838408_1393019557659656_1416375085_n.jpg' ],
    ['Oak and Pine Alley', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfa1/t51.2885-15/e15/1922109_372370959599541_228477136_n.jpg' ],
    ['Judge Emil Edouard (Edward) Simon', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10881869_334271076759344_699704777_n.jpg' ],
    ['Evangeline Oak', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/10865118_808542965850504_2040511604_n.jpg' ],
    ['Site of Camp Pratt', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtf1/t51.2885-15/e15/10852612_797841366921566_734291525_n.jpg' ],
    ['Spanish Lake', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtp1/t51.2885-15/e15/10881789_1748804258678178_670040793_n.jpg' ],
    ['General ALfred Mouton', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-prn/t51.2885-15/e15/10853150_720872341331501_1932568026_n.jpg' ],
    ['Bltyewood Plantation', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10832145_1049306655095556_421243297_n.jpg' ],
    ['Church of the Incarnation', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfp1/t51.2885-15/e15/1599399_747993095279362_912481219_n.jpg' ],
    ['Indians Along Amite River', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpt1/t51.2885-15/e15/10843987_1505792603006764_398667935_n.jpg' ],
    ['It is a Replica of Our Lady of Lourdes Grotto', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-frc/t51.2885-15/e15/10831939_980284305334329_1665324389_n.jpg' ],
    ['The Episcopal Church of the Epiphany', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-frc/t51.2885-15/e15/10852867_890756774291610_642297593_n.jpg' ],
    ['New Iberia', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-frc/t51.2885-15/e15/10817731_1519454181638420_223041714_n.jpg' ],
    ['Frederic Henri Duperier', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-prn/t51.2885-15/e15/10802878_796409260424423_706018001_n.jpg' ],
    ['Felicite', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/10843693_1505415256407977_1271877733_n.jpg' ],
    ['The Erath Building', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-prn/t51.2885-15/e15/10802878_1510992202503885_1739456726_n.jpg' ],
    ['Opelousas: Capital of Conferate Louisiana', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10848105_1517066408558619_546732447_n.jpg' ],
    ['Site of Bowie Residence', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpa1/t51.2885-15/e15/928609_1525308017727930_1826858985_n.jpg' ],
    ['The Henry Wadsworth Longfellow Monument', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/10483585_1545453812335487_359700357_n.jpg' ],
    ['Bayou Vermilion', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xaf1/t51.2885-15/e15/10843900_814519688600523_1838187857_n.jpg' ],
    ['The Cathedral of Saint John the Evangelist', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xtp1/t51.2885-15/e15/10844251_1015863021772428_586167868_n.jpg' ],
    ['St. Cecilia School', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-ash/t51.2885-15/e15/10808482_1597638260459213_1511887155_n.jpg' ],
    ['Indian Camp Plantation', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xpt1/t51.2885-15/e15/10542013_1504271076518344_1461740298_n.jpg' ],
    ['St. Gabriel Church', 'https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xat1/t51.2885-15/e15/10808600_1512230862391349_915783202_n.jpg' ],
]


#curl -F "title=Plessy V. Ferguson" -F "description=Press Street Railroad Yards<p>Site of the arrest of Home Adolph Plessy. <p>Submitted by <a href='https://www.instagram.com/alwaysreadtheplaque/'>@alwaysreadtheplaque</a>." -F "lat=44" -F "lng=46" -F "plaque_image_url=https://instagram.fsnc1-1.fna.fbcdn.net/hphotos-xfp1/t51.2885-15/sh0.08/e35/12446013_955204321194540_1183267577_n.jpg" http://readtheplaque.com/add 


    #fmt = '''curl -F "title=%s" -F "description= <p>Submitted by <a href='https://www.instagram.com/alwaysreadtheplaque/'>@alwaysreadtheplaque</a>." -F "lat=44" -F "lng=46" -F "plaque_image_url=%s" http://readtheplaque.com/add'''
    #txt = fmt % (title, url)

add_url = 'http://readtheplaque.com/add'

for img_url in img_urls:
    title = img_url[0]
    url = img_url[1]
    values = {
        'title': title,
        'plaque_image_url': url,
        'description': '<p>Submitted by <a href="https://www.instagram.com/alwaysreadtheplaque/">@alwaysreadtheplaque</a>.',
        'lat': 44.0,
        'lng': 46.0,
    }
    #html_out = urllib.urlopen(add_url, urllib.urlencode(values)).read()
    response = requests.post(add_url, values)
    print title, url, response.status_code


