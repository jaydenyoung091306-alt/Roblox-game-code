local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HttpService = game:GetService("HttpService")

local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local PetDatabase = require(ReplicatedStorage.Modules.PetDatabase)
local Util = require(ReplicatedStorage.Modules.Util)

local DataService = require(script.Parent.DataService)

local GachaService = {}

local petsByRarity = {}
for _, pet in ipairs(PetDatabase) do
	petsByRarity[pet.rarity] = petsByRarity[pet.rarity] or {}
	table.insert(petsByRarity[pet.rarity], pet)
end

function GachaService.RollPet(player)
	local profile = DataService.Get(player)
	if not profile then
		return false, "Data not loaded yet"
	end

	if profile.Cash < GameConfig.GachaCashCost then
		return false, "Not enough cash"
	end

	local rarity = Util.WeightedPick(GameConfig.Rarities)
	local race = Util.WeightedPick(GameConfig.Races)
	local trait = Util.WeightedPick(GameConfig.Traits)

	local pool = petsByRarity[rarity.name]
	local species = pool[math.random(1, #pool)]

	profile.Cash -= GameConfig.GachaCashCost

	local pet = {
		uid = HttpService:GenerateGUID(false),
		speciesId = species.id,
		rarity = rarity.name,
		race = race.name,
		trait = trait.name,
	}

	table.insert(profile.Pets, pet)

	return true, pet
end

return GachaService
