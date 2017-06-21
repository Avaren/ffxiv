import asyncio
import functools
import logging
import re

import itertools
import lxml.html

log = logging.getLogger(__name__)

# TODO: Other regions?
BASE_URL = 'http://eu.finalfantasyxiv.com/lodestone'

FFXIV_CLASSES = [
    ('Tank', ['Paladin', 'Gladiator', 'Warrior', 'Marauder', 'Dark Knight']),
    ('Healer', ['White Mage', 'Conjurer', 'Scholar', 'Astrologian']),
    ('Melee DPS', ['Monk', 'Pugilist', 'Dragoon', 'Lancer', 'Ninja', 'Rogue', 'Samurai']),
    ('Physical Ranged DPS', ['Bard', 'Archer', 'Machinist']),
    ('Magical Ranged DPS', ['Black Mage', 'Thaumaturge', 'Summoner', 'Arcanist', 'Red Mage']),
    ('Disciples of the Land', ['Miner', 'Botanist', 'Fisher']),
    ('Disciples of the Hand',
     ['Carpenter', 'Blacksmith', 'Armorer', 'Goldsmith', 'Leatherworker', 'Weaver', 'Alchemist', 'Culinarian']),

]

ARM_PREFIXES = ['Two-handed ', 'One-handed ', "'s Arm", "'s Primary Tool", "'s Grimoire"]

FFXIV_ELEMENTS = ['fire', 'ice', 'wind', 'earth', 'lightning', 'water']

FFXIV_PROPS = ['Defense', 'Parry', 'Magic Defense',
               'Attack Power', 'Skill Speed',
               'Slashing', 'Piercing', 'Blunt',
               'Attack Magic Potency', 'Healing Magic Potency', 'Spell Speed',
               'Morale',
               'Accuracy', 'Critical Hit Rate', 'Determination',
               'Craftsmanship', 'Control']


def search_character(html, character_name):
    data = lxml.html.fromstring(html)

    for tag in data.findall(".//a[@class='entry__link']"):
        if tag.find(".//p[@class='entry__name']").text.lower() == character_name.lower():
            return re.findall(r'(\d+)', tag.attrib['href'])[0]




def parse_character(html):
    data = lxml.html.fromstring(html)

    # Name, Server, Title
    char_box = data.find(".//a[@class='frame__chara__link']")
    name = char_box.find(".//p[@class='frame__chara__name']").text.strip()
    server = char_box.find(".//p[@class='frame__chara__world']").text.strip()
    portrait_url = char_box.find("./div[@class='frame__chara__face']/img").attrib['src'].rsplit('?', 1)[0]

    try:
        title = char_box.find(".//p[@class='frame__chara__title']").text.strip()
    except (AttributeError, IndexError):
        title = None

    profile_boxes = data.findall(".//div[@class='character__profile__data__detail']/div[@class='character-block']")

    # Race, Tribe, Gender
    race_ele = profile_boxes[0].find(".//p[@class='character-block__name']")
    race = race_ele.text
    clan, gender = race_ele.getchildren()[0].tail.split('/')
    gender = 'male' if gender.strip('\n\t ')[-1] == u'\u2642' else 'female'

    race = race.strip()
    clan = clan.strip()

    # Nameday & Guardian
    nameday_text = profile_boxes[1].find(".//p[@class='character-block__birth']").text
    nameday = re.findall('(\d+)', nameday_text)
    nameday = {
        'sun': int(nameday[0]),
        'moon': (int(nameday[1]) * 2) - (0 if 'Umbral' in nameday_text else 1),
    }
    guardian = profile_boxes[1].find(".//p[@class='character-block__name']").text

    # City-state
    citystate = profile_boxes[2].find(".//p[@class='character-block__name']").text

    # Grand Company
    try:
        grand_company = profile_boxes[3].find(".//p[@class='character-block__name']").text.split('/')
    except (AttributeError, IndexError):
        grand_company = None

    # Free Company
    try:
        fc_link = profile_boxes[4].find(".//div[@class='character__freecompany__name']//a")
        free_company = {
            'id': re.findall('(\d+)', fc_link.attrib['href'])[0],
            'name': fc_link.text,
            'crest': [x.attrib['src'] for x in
                      profile_boxes[4].findall(".//div[@class='character__freecompany__crest__image']/img")]
        }
    except (AttributeError, IndexError):
        free_company = None

    class_items = itertools.chain.from_iterable(n.findall(".//ul[@class='character__job clearfix']/li")
                   for n in data.findall(".//div[@class='character__job__role']"))

    # Classes
    classes = {}
    for class_item in class_items:
        try:
            cls = class_item.xpath("./div[contains(@class, 'character__job__name')]")[0].text_content().strip()

            if not cls:
                continue

            level = class_item.find("./div[@class='character__job__level']").text_content().strip()

            # if level == '-':
            #     level = 0
            #     # exp = 0
            #     # exp_next = 0
            # else:
            level = 0 if level == '-' else int(level)
            # exp = int(tag.next_sibling.next_sibling.next_sibling.next_sibling.text.split(' / ')[0])
            # exp_next = int(tag.next_sibling.next_sibling.next_sibling.next_sibling.text.split(' / ')[1])

            classes[cls] = dict(level=level)
        except:
            print(lxml.html.tostring(class_item))

    # Stats
    stats = {}

    # images = soup.select("img")

    # for img in images:
    #     m = re.search('/images/character/attribute_([a-z]{3})', img.get('src'))
    #     if m and m.group(1) and m.group(1) in ('str', 'dex', 'vit', 'int', 'mnd', 'pie'):
    #         stats[m.group(1)] = img.parent.select("span")[0].text

    main_params = data.find(".//div[@class='character__param']")
    for attribute in ('hp', 'mp', 'cp', 'tp'):
        stats[attribute] = 0

    for tag in main_params.findall('.//div'):
        stat_name, stat_no = tag.getchildren()
        stats[stat_name.text.lower()] = int(stat_no.text)

    params = data.findall(".//div[@class='character__profile__data']//table[@class='character__param__list']//tr")
    for param in params:
        stat_name, stat_no = param.getchildren()
        stats[stat_name.getchildren()[0].text.lower()] = int(stat_no.text)

    avatar_url = data.find(".//div[@class='character__detail__image']/a").attrib['href'].rsplit('?', 1)[0]

    # for element in FFXIV_ELEMENTS:
    #     tooltip = 'Decreases %s-aspected damage.' % element
    #     ele_value = int(soup.find(title=tooltip).parent.select('.val')[0].text)
    #     stats[element] = ele_value
    #
    # for prop in FFXIV_PROPS:
    #     try:
    #         stats[prop] = int(soup.find(text=prop, class_='left').parent.parent.select('.right')[0].text)
    #     except AttributeError:
    #         pass
    #
    # # minions and mounts both use "minion_box", which is stupid
    # minion_type = 0
    # minions = []
    # mounts = []
    # for minionbox in soup.select('.minion_box'):
    #     for minionbox_entry in minionbox.select('a'):
    #         if minion_type:
    #             minions.append(minionbox_entry['title'])
    #         else:
    #             mounts.append(minionbox_entry['title'])
    #     minion_type = 1
    #
    # # Equipment
    current_class = None
    current_job = None

    arm_name = data.find(".//div[@class='character__class__arms']//p[@class='db-tooltip__item__category']").text
    for arm_prefix in ARM_PREFIXES:
        arm_name = arm_name.replace(arm_prefix, '')
    current_class = arm_name

    crystal_items = data.xpath(
        ".//div[@class='character__detail__icon']//p[@class='db-tooltip__item__category' and text() = 'Soul Crystal']")
    if crystal_items:
        current_job = crystal_items[0].getparent().getchildren()[1].text[12:]

    # parsed_equipment = []
    #
    # equipment_tags = soup.select('.db-tooltip__item__txt')
    # equipment_tags = equipment_tags[: len(equipment_tags) // 2]
    #
    # for i, tag in enumerate(equipment_tags):
    #     item_tags = tag.select('.db-tooltip__item__name')
    #
    #     if item_tags:
    #
    #         if i == 0:
    #             slot_name = tag.select('.db-tooltip__item__category')[0].string.strip()
    #             slot_name = slot_name.replace('Two-handed ', '')
    #             slot_name = slot_name.replace('One-handed ', '')
    #             slot_name = slot_name.replace("'s Arm", '')
    #             slot_name = slot_name.replace("'s Primary Tool", '')
    #             slot_name = slot_name.replace("'s Grimoire", '')
    #             current_class = slot_name
    #         elif tag.select('.db-tooltip__item__category')[0].string.strip() == 'Soul Crystal':
    #             current_job = item_tags[0].text[12:]
    #
    #         # strip out all the extra \t and \n it likes to throw in
    #         parsed_equipment.append(' '.join(item_tags[0].text.split()))
    #     else:
    #         parsed_equipment.append(None)

    # equipment = parsed_equipment[:len(parsed_equipment) // 2]

    return {
        'name': name,
        'server': server,
        'title': title,

        'race': race,
        'clan': clan,
        'gender': gender,

        # 'legacy': len(soup.select('.bt_legacy_history')) > 0,

        'avatar_url': avatar_url,
        'portrait_url': portrait_url,

        'nameday': nameday,
        'guardian': guardian,

        'citystate': citystate,

        'grand_company': grand_company,
        'free_company': free_company,

        'classes': classes,
        'stats': stats,

        # 'achievements': self.scrape_achievements(lodestone_id),

        # 'minions': minions,
        # 'mounts': mounts,

        'current_class': current_class,
        'current_job': current_job,
        # 'current_equipment': parsed_equipment,
    }


def parse_free_company(html):
    tree = lxml.html.fromstring(html).find(".//div[@class='ldst__window']")

    fc_box = tree.find(".//a[@class='entry__freecompany']")

    name = fc_box.find(".//p[@class='entry__freecompany__name']").text
    grand_company, server = [e.text.strip() for e in fc_box.findall(".//p[@class='entry__freecompany__gc']")]
    crest = [x.attrib['src'] for x in
             fc_box.findall(".//div[@class='entry__freecompany__crest__image']/img")]

    fc_tag = tree.find(".//p[@class='freecompany__text freecompany__text__tag']").text

    formed = tree.xpath(".//h3[@class='heading--lead' and text()='Formed']")[0].getnext().getchildren()[1].text
    if formed:
        m = re.search(r'ldst_strftime\(([0-9]+),', formed)
        if m.group(1):
            formed = m.group(1)
    else:
        formed = None

    slogan = tree.find("p[@class='freecompany__text freecompany__text__message']").text_content()
    # slogan = ''.join(x.strip().replace('<br/>', '\n') for x in slogan) if slogan else ""

    # active = soup.find(text='Active').parent.parent.select('td')[0].text.strip()
    # recruitment = soup.find(text='Recruitment').parent.parent.select('td')[0].text.strip()
    active_members = tree.xpath(".//h3[@class='heading--lead' and text()='Active Members']")[0].getnext().text
    rank = tree.xpath(".//h3[@class='heading--lead' and text()='Rank']")[0].getnext().text

    # focus = []
    # for f in soup.select('.focus_icon li img'):
    #     on = not (f.parent.get('class') and 'icon_off' in f.parent.get('class'))
    #     focus.append(dict(on=on,
    #                       name=f.get('title'),
    #                       icon=f.get('src')))
    #
    # seeking = []
    # for f in soup.select('.roles_icon li img'):
    #     on = not (f.parent.get('class') and 'icon_off' in f.parent.get('class'))
    #     seeking.append(dict(on=on,
    #                         name=f.get('title'),
    #                         icon=f.get('src')))

    estate_name = tree.find("p[@class='freecompany__estate__name']")
    if estate_name is not None:
        greeting = tree.find("p[@class='freecompany__estate__greeting']").text_content()
        estate = {
            'name': estate_name.text,
            'address': tree.find("p[@class='freecompany__estate__text']").text,
            'greeting': '' if greeting == 'No greeting available.' else greeting,
        }
    else:
        estate = None

    try:
        ranking_week, ranking_month = tree.findall(
            ".//table[@class='character__ranking__data parts__space--reset']//th")
        ranking = {
            'week': re.findall('(\d+)', ranking_week.text)[0],
            'month': re.findall('(\d+)', ranking_month.text)[0],
        }
    except:
        pass

    return {
        'name': name,
        'server': server,
        'grand_company': grand_company,
        # 'friendship': friendship,
        'slogan': slogan,
        'tag': fc_tag,
        'formed': formed,
        'crest': crest,
        # 'active': active,
        # 'recruitment': recruitment,
        'active_members': active_members,
        'rank': rank,
        # 'focus': focus,
        # 'seeking': seeking,
        'estate': estate,
        'ranking': ranking,
    }


def parse_free_company_members(html):
    tree = lxml.html.fromstring(html).find(".//div[@class='ldst__window']")

    roster = []

    for i, member in enumerate(tree.xpath("./ul[not(@class)]/li/a")):
        # div/div[@class='entry__freecompany__center']
        member = {
            'name': member.find(".//p[@class='entry__name']").text,
            'lodestone_id': re.findall('(\d+)', member.attrib['href'])[0],
            'rank': member.find(".//ul[@class='entry__freecompany__info']//span").text,
            'leader': True if i == 0 else False
        }

        roster.append(member)

    # TODO Pagination


    # try:
    #     pages = int(soup.find(attrs={'rel': 'last'})['href'].rsplit('=', 1)[-1])
    # except TypeError:
    #     pages = 1
    #
    # if pages > 1:
    #     pool = Pool(5)
    #     for page in xrange(2, pages + 1):
    #         pool.spawn(populate_roster, page)
    #     pool.join()

    return roster


async def search_thing(session, thing, server_name, thing_name):
    url = BASE_URL + '/' + thing

    params = dict(q=thing_name, worldname=server_name.title())

    async with session.get(url, params=params) as req:
        log.info("GET => {}".format(req.url))
        if req.status == 200:
            text = await req.text()
            f = functools.partial(search_character, text, thing_name)
            char_id = await asyncio.get_event_loop().run_in_executor(None, f)
            if char_id:
                return char_id

    raise RuntimeError('Not found.')
