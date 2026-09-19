local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local PetDatabase = require(ReplicatedStorage.Modules.PetDatabase)
local Util = require(ReplicatedStorage.Modules.Util)

local DataService = require(script.Parent.DataService)

local PetService = {}

function PetService.FindPet(profile, uid)
	for _, pet in ipairs(profile.Pets) do
		if pet.uid == uid then
			return pet
		end
	end
	return nil
end

function PetService.IsEquipped(profile, uid)
	for _, equippedUid in ipairs(profile.EquippedPetUids) do
		if equippedUid == uid then
			return true
		end
	end
	return false
end

function PetService.Equip(player, uid)
	local profile = DataService.Get(player)
	if not profile then
		return false, "Data not loaded yet"
	end

	local pet = PetService.FindPet(profile, uid)
	if not pet then
		return false, "Pet not found"
	end

	if PetService.IsEquipped(profile, uid) then
		return false, "Pet already equipped"
	end

	if #profile.EquippedPetUids >= profile.MaxPetSlots then
		return false, "No free pet slots"
	end

	table.insert(profile.EquippedPetUids, uid)
	return true
end

function PetService.Unequip(player, uid)
	local profile = DataService.Get(player)
	if not profile then
		return false, "Data not loaded yet"
	end

	for i, equippedUid in ipairs(profile.EquippedPetUids) do
		if equippedUid == uid then
			table.remove(profile.EquippedPetUids, i)
			return true
		end
	end

	return false, "Pet was not equipped"
end

function PetService.RerollRace(player, uid)
	local profile = DataService.Get(player)
	if not profile then
		return false, "Data not loaded yet"
	end

	if not profile.Upgrades["racereroll"] then
		return false, "Race reroll is not unlocked yet"
	end

	if profile.Gems < GameConfig.RaceRerollGemCost then
		return false, "Not enough gems"
	end

	local pet = PetService.FindPet(profile, uid)
	if not pet then
		return false, "Pet not found"
	end

	profile.Gems -= GameConfig.RaceRerollGemCost
	pet.race = Util.WeightedPick(GameConfig.Races).name

	return true, pet
end

function PetService.RerollTrait(player, uid)
	local profile = DataService.Get(player)
	if not profile then
		return false, "Data not loaded yet"
	end

	if not profile.Upgrades["traitreroll"] then
		return false, "Trait reroll is not unlocked yet"
	end

	if profile.Gems < GameConfig.TraitRerollGemCost then
		return false, "Not enough gems"
	end

	local pet = PetService.FindPet(profile, uid)
	if not pet then
		return false, "Pet not found"
	end

	profile.Gems -= GameConfig.TraitRerollGemCost
	pet.trait = Util.WeightedPick(GameConfig.Traits).name

	return true, pet
end

function PetService.GetEffectiveStats(profile, pet)
	local species = Util.FindByField(PetDatabase, "id", pet.speciesId)
	local race = Util.FindByField(GameConfig.Races, "name", pet.race)
	local trait = Util.FindByField(GameConfig.Traits, "name", pet.trait)

	local tycoonDamageMult = 1
	local tycoonCashMult = 1
	for _, upgrade in ipairs(GameConfig.TycoonUpgrades) do
		if profile.Upgrades[upgrade.id] then
			if upgrade.effect.type == "damageMult" then
				tycoonDamageMult += upgrade.effect.value
			elseif upgrade.effect.type == "cashMult" then
				tycoonCashMult += upgrade.effect.value
			end
		end
	end

	local damage = species.baseDamage * race.multiplier * trait.damageMult * tycoonDamageMult
	local cashMult = race.multiplier * trait.cashMult * tycoonCashMult
	local attackInterval = GameConfig.PlayerBaseAttackInterval / trait.speedMult
	local dropMult = trait.dropMult

	return {
		species = species,
		race = race,
		trait = trait,
		damage = damage,
		cashMult = cashMult,
		attackInterval = attackInterval,
		dropMult = dropMult,
	}
end

return PetService
