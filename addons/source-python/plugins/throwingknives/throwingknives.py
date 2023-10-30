#	Config
from config.manager import ConfigManager
#	Players
from players.entity import Player
from players.helpers import index_from_userid
from players.dictionary import PlayerDictionary
from filters.players import PlayerIter
#	Event
from events import Event
#	Entity
from entities.entity import Entity
#	Hooks
from entities.hooks import EntityPreHook, EntityCondition
#	Messages
from messages import HintText

with ConfigManager('throwingknives') as addon_config:
	DAMAGE = addon_config.cvar('throwingknives_damage', 20, 'How much damage knife makes')
	TIMER = addon_config.cvar('throwingknives_delay', 30, 'How long takes to generate a knife')
	SPAWN_KNIVES = addon_config.cvar('throwingknives_spawn', 3, 'How many knives player spawns with')
	KILL = addon_config.cvar('throwingknives_kill', 1, 'Should thrown knife kill give new knife')
	KILL_KNIFE = addon_config.cvar('throwingknives_kill_knives', 3, 'How many knives gives per kill kill. Requires throwingknives_kill to be 1')


delay = PlayerDictionary()

NO_KNIFES = HintText('You do not have any throwingknives!')
KNIFES_GAINED = HintText('You have been given +1 throwingknive!')
KNIFE_HIT =  HintText(f'You have hitted {DAMAGE.get_int()}')

class KnifePlayer(Player):
	def __init__(self, index, caching=True):
		super().__init__(index)
		self.knives = 0

	def adjust_spawn(self):
		if self.team_index < 2:
			return

		self.knives = SPAWN_KNIVES.get_int()

	def throw_knife(self):
		global current_knife
		current_knives = self.knives

		if current_knives > 0:
			current_knives -= 1
			if current_knives == 0:
				current_knives = 0
			self.knives = current_knives

			HintText(f'You have {current_knives} throwingknives remaining!').send(self.index)

			entity = Entity.create('weapon_knife')
			entity.origin = self.eye_location + self.view_vector
			entity.angles = self.angles
			entity.target_name = f'thrown_knife_{self.index}'
			entity.spawn()
			entity.teleport(velocity=self.view_vector * 1600)
			entity.delay(1.5, entity.remove)

			index = self.index

			stop_delay(index)
			start_delay(index)

		else:
			NO_KNIFES.send(self.index)

	def give_knife_kill(self):
		if KILL.get_int() == 1:
			if self.dead:
				return

			self.knives += KILL_KNIFE.get_int()
			KNIFES_GAINED.send(self.index)

	def generate_knife(self):
		if self.dead:
			return
		self.knives += 1
		KNIFES_GAINED.send(self.index)

def start_delay(index):
	player = KnifePlayer(index)
	delay[index] = player.delay(TIMER.get_float(), player.generate_knife)

def stop_delay(index):
	if index in delay and delay[index].running:
		delay[index].cancel()

@Event('player_spawn')
def player_spawn(args):
	userid = args.get_int('userid')
	KnifePlayer.from_userid(userid).adjust_spawn()

@Event('player_death')
def player_death(args):
	index = index_from_userid(args.get_int('userid'))
	stop_delay(index)

@Event('round_end')
def round_end(args):
	for player in PlayerIter('human'):
		stop_delay(player.index)

@Event('weapon_fire')
def weapon_fire(args):
	if args.get_string('weapon') == 'knife':
		userid = args.get_int('userid')
		KnifePlayer.from_userid(userid).throw_knife()

@EntityPreHook(EntityCondition.equals_entity_classname('weapon_knife'), 'start_touch')
def knife_touch_pre(stack_data):
	entity = Entity._obj(stack_data[0])
	target_name = entity.target_name
	if not target_name.startswith('thrown_knife'):
		return

	try:
		player = KnifePlayer(int(target_name.split('_')[2]))
	except ValueError:
		return

	index = player.index

	dmg = DAMAGE.get_int()

	target = Entity._obj(stack_data[1])
	if not target.is_player():
		return

	target = Player(target.index)
	if player.team == target.team:
		return

	entity.call_input('Kill')

	if dmg >= target.health:
		target.take_damage(damage=dmg, attacker_index=index, weapon_index=Entity.find_or_create('weapon_knife').index)
		player.give_knife_kill()
	else:
		target.take_damage(damage=dmg, attacker_index=index)
	KNIFE_HIT.send(index)
