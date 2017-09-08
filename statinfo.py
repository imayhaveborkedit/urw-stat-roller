from textwrap import dedent as dd

names = (
    'Intelligence',
    'Will',
    'Strength',
    'Endurance',
    'Dexterity',
    'Agility',
    'Speed',
    'Eyesight',
    'Hearing',
    'Smell/Taste',
    'Touch',
    'Height',
    'Weight',
    'Physique'
)

groups = (
    ('Intelligence', 'Will'),
    ('Strength',
     'Endurance',
     'Dexterity',
     'Agility',
     'Speed',
     'Eyesight',
     'Hearing',
     'Smell/Taste',
     'Touch'),
     ('Height', 'Weight'),
     ('Physique',)
)

# TODO: Figure out how to determine chosen race and give stat info
# http://cloud-3.steamusercontent.com/ugc/320124788920141475/83A5568F35B91FC2BD926876D7757487797911CF/

extra_info = {
    'Intelligence': dd(
        '''
        Intelligence primarily affects how quickly you train skills.

        The following skills are governed by this stat:
        Agriculture,
        Building,
        Herblore,
        Physician,
        Ritual,
        Trapping,
        Weatherlore
        '''
    ),

    'Will': dd(
        '''
        Will affects your ability to stay awake when exhausted and your abiliity
        to force yourself to eat raw meat and fish (and then throwing up).

        The following skills are governed by this stat:
        Agriculture,
        Fishing,
        Physician,
        Ritual,
        Stealth
        '''
    ),

    'Strength': dd(
        '''
        Strength does NOT affect your carrying capacity.

        The following skills are governed by this stat:
        Club*,
        Building,
        Timbercraft,
        Climbing,
        Swimming,
        Shield,
        Sword,
        Axe,
        Flail,
        Spear,
        Bow,
        Unarmed

        * Club skill level accounts for 2x your Strength level.
        ((2*Strength + Dexterity)/3 * skill points)
        '''
    ),

    'Endurance': dd(
        '''
        Endurance affects your Encumberance penalty (and thus Mobility) via
        reduced Fatigue gain and increased recovery speed.  Fatigue acts as
        flat reduction to skill levels.  It also affects your pain tolerance,
        or resistance to being hit and losing consciousness.

        The following skills are governed by this stat:
        Agriculture,
        Swimming
        '''
    ),

    'Dexterity': dd(
        '''
        Dexterity affects the likelyhood of fumbling when in combat.

        The following skills are governed by this stat:
        Agriculture,
        Carpentry,
        Fishing,
        Hideworking*,
        Timbercraft,
        Trapping,
        Climbing,
        Skiing,
        Knife,
        Sword,
        Shield,
        Flail,
        Bow,
        Crossbow

        * Hideworking skill level accounts for 2x your Dexterity level.
        '''
    ),

    'Agility': dd(
        '''
        Agility is one of the few stats that governs your Dodge skill,
        *supposedly* with a higher than average multiplier as well.
        It also helps when standing up in the heat of combat.

        The following skills are governed by this stat:
        Dodge,
        Timbercraft,
        Climbing,
        Skiing*,
        Swimming,
        Stealth,
        Shield,
        Unarmed,
        Knife,
        Sword,
        Axe,
        Spear*,
        Club,
        Flail

        * Skiing and Spear skill levels account for 2x your Agility level.
        '''
    ),

    'Speed': dd(
        '''
        Speed affects your base Mobility value (5x Speed).  This means
        walking, running, paddling a raft/punt, swimming hiding and crawling.

        *Supposedly* Speed also affects how long it takes to rest.

        The following skills are governed by this stat:
        Dodge,
        Unarmed
        '''
    ),

    'Eyesight': dd(
        '''
        Eyesight affects how far you can see on the maps, and how close you have to be
        to spot the outline of a beast or man in the distance on the wilderness map.

        The following skills are governed by this stat:
        Weatherlore,
        Tracking*,
        Dodge,
        Shield,
        Bow,
        Crossbow

        * Tracking skill level accounts for 2x your Eyesight level.
        '''
    ),

    'Hearing': dd(
        '''
        Hearing affects your ability to locate your prey on a partly obscured map, as well as
        warn you of danger outside your line of sight. A deaf character will -potentially-
        be in danger of being eaten alive by squirrels while sleeping outdoors. Or by wolves.

        The following skills are governed by this stat:
        Ritual,
        Tracking
        '''
    ),

    'Smell/Taste': dd(
        '''
        Smell/Taste affects your ability to differentiate between cow milk and bull milk. :^)

        The following skills are governed by this stat:
        Cookery*,
        Herblore,
        Weatherlore,
        Hideworking,
        Tracking

        * Cookery skill level accounts for 2x your Smell/Taste level.
        '''
    ),

    'Touch': dd(
        '''
        The following skills are governed by this stat:
        Building,
        Carpentry,
        Cookery,
        Fishing,
        Herblore,
        Hideworking,
        Physician*,
        Trapping,
        Weatherlore,
        Climbing,
        Stealth,
        Knife,
        Flail,
        Crossbow

        * Physician skill level accounts for 2x your Touch level.

        '''
    ),

    'Height': dd(
        '''
        Indirectly affects your Weight.
        '''
    ),

    'Weight': dd(
        '''
        Weight is a combination of height and physique (or was at least).
        Worn armor and clothes cause an Encumberance penalty when their total
        weight exceeds 10% of your weight.  *Supposedly* your weight limit
        is calculated as such:

        weight_limit = character_weight * 1.5
        '''
    ),

    'Physique': dd(
        '''
        Physique has since been removed from the game but still seems to exist in
        memory.  It is unknown if this mechanic is still in the game since its
        removal from the stats screen during character creation.

        Physique used to affect your weight limit and ability to pick up
        items, i.e. a large physique would allow you to pick up large items with ease
        while a small one would mean trouble picking up a punt.  Physique may have
        also affected how well you dealt with starvation.  Speed and stealth were
        also supposedly affected by having a small physique.
        '''
    ),
}

class _stat:
    def __init__(self, name, buffername=None):
        self.name = name
        self.buffername = (buffername or self.name.upper()) + '_STAT_BUFFER'
        self.extra_info = extra_info.get(self.name, None)

    def format(self, value):
        return Stats.format(self.name, value)

    def __repr__(self):
        return f'<_stat {self.name} ({self.buffername}), extra_info={bool(self.extra_info)}>'

class Stats:
    intelligence = _stat('Intelligence')
    will = _stat('Will')

    strength = _stat('Strength')
    endurance = _stat('Endurance')
    dexterity = _stat('Dexterity')
    agility = _stat('Agility')
    speed = _stat('Speed')
    eyesight = _stat('Eyesight')
    hearing = _stat('Hearing')
    smelltaste = _stat('Smell/Taste', buffername='SMELLTASTE')
    touch = _stat('Touch')

    height = _stat('Height')
    weight = _stat('Weight')

    physique = _stat('Physique')

    rerolls = _stat('Rerolls')

    _fmt =  '{stat:<13} {val:>2} [{size:<18}]'
    _hfmt = '{stat:<13} {val:>2}" ({fval}\'{ival}")'
    _wfmt = '{stat:<13} {val:>2} lbs ({kval} kg)'
    _pfmt = '{stat:<13} Type {val} [ {size} ]'
    _rfmt = '{stat:<13} {val}'


    @classmethod
    def get(cls, name, *, group=None):
        if group is None:
            group = cls.all_stats

        try:
            return next(filter(lambda s: s.name == name, group()))
        except StopIteration:
            pass

    @classmethod
    def get_name(cls, buffname, *, group=None):
        if group is None:
            group = cls.all_stats

        try:
            return next(filter(lambda s: s.buffername == buffname, group()))
        except StopIteration:
            pass
            

    @classmethod
    def all_stats(cls):
        """
        Return a tuple of all stats with memory locations.
        """
        return (
            cls.intelligence, cls.will, cls.strength, cls.endurance,
            cls.dexterity, cls.agility, cls.speed, cls.eyesight,
            cls.hearing, cls.smelltaste, cls.touch, cls.height,
            cls.weight, cls.physique, cls.rerolls)

    @classmethod
    def all_real_stats(cls):
        """
        Return a tuple of all stats, not including rerolls.
        """
        return (
            cls.intelligence, cls.will, cls.strength, cls.endurance,
            cls.dexterity, cls.agility, cls.speed, cls.eyesight,
            cls.hearing, cls.smelltaste, cls.touch, cls.height,
            cls.weight, cls.physique)

    @classmethod
    def all_normal_stats(cls):
        """
        Return a tuple of all stats that can have values of 1 to 18.
        """
        return (
            cls.intelligence, cls.will, cls.strength, cls.endurance,
            cls.dexterity, cls.agility, cls.speed, cls.eyesight,
            cls.hearing, cls.smelltaste, cls.touch)


    @classmethod
    def format(cls, stat, value):
        try:
            return getattr(cls, '_format_%s' % stat.lower())(value)
        except AttributeError:
            return cls._fmt.format(
                stat=stat + ':', val=value, size='='*value)

    @classmethod
    def _format_height(cls, value):
        f, i = divmod(value, 12)
        return cls._hfmt.format(
            stat=cls.height.name + ':', val=value, fval=f, ival=i)

    @classmethod
    def _format_weight(cls, value):
        k = round(value * 0.4535, 1)
        return cls._wfmt.format(
            stat=cls.weight.name + ':', val=value, kval=k)

    @classmethod
    def _format_physique(cls, value):
        things = list('-----')
        try:
            things[value-1] = '@'
        except IndexError:
            pass

        size = ' '.join(things)
        return cls._pfmt.format(
            stat=cls.physique.name + ':', val=value, size=size)

    @classmethod
    def _format_rerolls(cls, value):
        return cls._rfmt.format(stat=cls.rerolls.name + ':', val=value)
