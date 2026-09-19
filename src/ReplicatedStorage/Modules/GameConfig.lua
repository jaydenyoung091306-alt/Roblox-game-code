local GameConfig = {}

GameConfig.StartingCash = 100
GameConfig.StartingGems = 0
GameConfig.MaxPetSlotsBase = 1

GameConfig.GachaCashCost = 100

GameConfig.AttackRange = 22
GameConfig.PlayerBaseAttackInterval = 1.2

GameConfig.Rarities = {
	{ name = "Common", weight = 60, color = Color3.fromRGB(200, 200, 200) },
	{ name = "Rare", weight = 25, color = Color3.fromRGB(85, 170, 255) },
	{ name = "Epic", weight = 12, color = Color3.fromRGB(170, 85, 255) },
	{ name = "Legendary", weight = 3, color = Color3.fromRGB(255, 170, 0) },
}

GameConfig.Races = {
	{ name = "Normal", weight = 70, multiplier = 1.0, color = Color3.fromRGB(235, 235, 235) },
	{ name = "Golden", weight = 20, multiplier = 1.5, color = Color3.fromRGB(255, 215, 0) },
	{ name = "Rainbow", weight = 8, multiplier = 2.0, color = Color3.fromRGB(255, 80, 220) },
	{ name = "Shiny", weight = 2, multiplier = 3.0, color = Color3.fromRGB(80, 255, 255) },
}
GameConfig.RaceRerollGemCost = 250

GameConfig.Traits = {
	{ name = "Neutral", weight = 40, damageMult = 1.0, cashMult = 1.0, speedMult = 1.0, dropMult = 1.0 },
	{ name = "Swift", weight = 20, damageMult = 1.0, cashMult = 1.0, speedMult = 1.5, dropMult = 1.0 },
	{ name = "Tanky", weight = 20, damageMult = 1.2, cashMult = 1.0, speedMult = 0.8, dropMult = 1.0 },
	{ name = "Lucky", weight = 12, damageMult = 1.0, cashMult = 1.0, speedMult = 1.0, dropMult = 1.75 },
	{ name = "Greedy", weight = 8, damageMult = 0.9, cashMult = 1.5, speedMult = 1.0, dropMult = 1.0 },
}
GameConfig.TraitRerollGemCost = 250

-- effect.type: "petSlot" | "damageMult" | "cashMult" | "unlock" | "passiveIncome"
GameConfig.TycoonUpgrades = {
	{ id = "slot2", name = "2nd Pet Slot", cost = 500, effect = { type = "petSlot", value = 2 } },
	{ id = "slot3", name = "3rd Pet Slot", cost = 2500, effect = { type = "petSlot", value = 3 } },
	{ id = "slot4", name = "4th Pet Slot", cost = 10000, effect = { type = "petSlot", value = 4 } },
	{ id = "dmg1", name = "Damage Boost I", cost = 750, effect = { type = "damageMult", value = 0.15 } },
	{ id = "dmg2", name = "Damage Boost II", cost = 3000, effect = { type = "damageMult", value = 0.25 } },
	{ id = "dmg3", name = "Damage Boost III", cost = 12000, effect = { type = "damageMult", value = 0.35 } },
	{ id = "cash1", name = "Cash Multiplier I", cost = 1000, effect = { type = "cashMult", value = 0.15 } },
	{ id = "cash2", name = "Cash Multiplier II", cost = 4000, effect = { type = "cashMult", value = 0.25 } },
	{ id = "cash3", name = "Cash Multiplier III", cost = 15000, effect = { type = "cashMult", value = 0.4 } },
	{ id = "racereroll", name = "Unlock Race Reroll", cost = 2000, effect = { type = "unlock", value = "raceReroll" } },
	{ id = "traitreroll", name = "Unlock Trait Reroll", cost = 2000, effect = { type = "unlock", value = "traitReroll" } },
	{ id = "dropper1", name = "Cash Dropper", cost = 1500, effect = { type = "passiveIncome", value = 5 } },
	{ id = "dropper2", name = "Cash Dropper II", cost = 6000, effect = { type = "passiveIncome", value = 15 } },
}
GameConfig.PassiveIncomeInterval = 5

GameConfig.PlotCount = 6
GameConfig.PlotSize = Vector3.new(48, 1, 48)
GameConfig.PlotSpacing = 64

return GameConfig
