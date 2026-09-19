local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")

local GameConfig = require(game:GetService("ReplicatedStorage").Modules.GameConfig)

local PlayerStore = DataStoreService:GetDataStore("SimulatorTycoon_PlayerData_v1")

local DataService = {}
local profiles = {}

local function defaultProfile()
	return {
		Cash = GameConfig.StartingCash,
		Gems = GameConfig.StartingGems,
		Pets = {},
		EquippedPetUids = {},
		MaxPetSlots = GameConfig.MaxPetSlotsBase,
		Upgrades = {},
		PlotId = nil,
	}
end

local function mergeMissingKeys(profile, defaults)
	for key, value in pairs(defaults) do
		if profile[key] == nil then
			profile[key] = value
		end
	end
	return profile
end

function DataService.Load(player)
	local success, result = pcall(function()
		return PlayerStore:GetAsync("Player_" .. player.UserId)
	end)

	local profile
	if success and result then
		profile = mergeMissingKeys(result, defaultProfile())
	else
		profile = defaultProfile()
	end

	profiles[player.UserId] = profile
	return profile
end

function DataService.Get(player)
	return profiles[player.UserId]
end

function DataService.Save(player)
	local profile = profiles[player.UserId]
	if not profile then
		return
	end

	local success, err = pcall(function()
		PlayerStore:SetAsync("Player_" .. player.UserId, profile)
	end)

	if not success then
		warn(("DataService: failed to save data for %s: %s"):format(player.Name, tostring(err)))
	end
end

function DataService.Remove(player)
	DataService.Save(player)
	profiles[player.UserId] = nil
end

function DataService.SaveAll()
	for _, player in ipairs(Players:GetPlayers()) do
		DataService.Save(player)
	end
end

return DataService
