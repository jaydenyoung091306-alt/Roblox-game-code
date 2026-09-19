local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Remotes = require(ReplicatedStorage.Modules.Remotes)
Remotes.CreateAll()

local Services = script.Parent.Services
local DataService = require(Services.DataService)
local GachaService = require(Services.GachaService)
local PetService = require(Services.PetService)
local TycoonService = require(Services.TycoonService)
local CombatService = require(Services.CombatService)
local MapBuilder = require(Services.MapBuilder)

local mapData = MapBuilder.Build()
TycoonService.Init(mapData.plots)
CombatService.Init()

local RollGacha = Remotes.Get("RollGacha")
local EquipPet = Remotes.Get("EquipPet")
local UnequipPet = Remotes.Get("UnequipPet")
local RerollRace = Remotes.Get("RerollRace")
local RerollTrait = Remotes.Get("RerollTrait")
local ProfileUpdated = Remotes.Get("ProfileUpdated")
local Notify = Remotes.Get("Notify")

local function pushProfile(player)
	local profile = DataService.Get(player)
	if profile then
		ProfileUpdated:FireClient(player, profile)
	end
end

local function setupLeaderstats(player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	leaderstats.Parent = player

	local cash = Instance.new("IntValue")
	cash.Name = "Cash"
	cash.Parent = leaderstats

	local gems = Instance.new("IntValue")
	gems.Name = "Gems"
	gems.Parent = leaderstats

	task.spawn(function()
		while player.Parent do
			local profile = DataService.Get(player)
			if profile then
				cash.Value = math.floor(profile.Cash)
				gems.Value = math.floor(profile.Gems)
			end
			task.wait(1)
		end
	end)
end

local function onPlayerAdded(player)
	DataService.Load(player)
	setupLeaderstats(player)
	TycoonService.AssignPlot(player)
	CombatService.SyncPets(player)
	pushProfile(player)

	player.CharacterAdded:Connect(function()
		task.wait(0.5)
		CombatService.SyncPets(player)
	end)
end

Players.PlayerAdded:Connect(onPlayerAdded)
for _, player in ipairs(Players:GetPlayers()) do
	onPlayerAdded(player)
end

Players.PlayerRemoving:Connect(function(player)
	CombatService.CleanupPlayer(player)
	TycoonService.ReleasePlot(player)
	DataService.Remove(player)
end)

game:BindToClose(function()
	DataService.SaveAll()
end)

RollGacha.OnServerInvoke = function(player)
	local success, result = GachaService.RollPet(player)
	if success then
		pushProfile(player)
		return { success = true, pet = result }
	end
	return { success = false, message = result }
end

EquipPet.OnServerEvent:Connect(function(player, uid)
	local success, err = PetService.Equip(player, uid)
	if success then
		CombatService.SyncPets(player)
		pushProfile(player)
	else
		Notify:FireClient(player, err, "error")
	end
end)

UnequipPet.OnServerEvent:Connect(function(player, uid)
	local success, err = PetService.Unequip(player, uid)
	if success then
		CombatService.SyncPets(player)
		pushProfile(player)
	else
		Notify:FireClient(player, err, "error")
	end
end)

RerollRace.OnServerInvoke = function(player, uid)
	local success, result = PetService.RerollRace(player, uid)
	if success then
		pushProfile(player)
		CombatService.SyncPets(player)
		return { success = true, pet = result }
	end
	return { success = false, message = result }
end

RerollTrait.OnServerInvoke = function(player, uid)
	local success, result = PetService.RerollTrait(player, uid)
	if success then
		pushProfile(player)
		CombatService.SyncPets(player)
		return { success = true, pet = result }
	end
	return { success = false, message = result }
end
