local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Debris = game:GetService("Debris")

local Remotes = require(ReplicatedStorage.Modules.Remotes)

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local screenGui = Instance.new("ScreenGui")
screenGui.Name = "SimulatorTycoonUI"
screenGui.ResetOnSpawn = false
screenGui.Parent = playerGui

local HUD = require(script.Parent.UI.HUD)
local GachaUI = require(script.Parent.UI.GachaUI)
local InventoryUI = require(script.Parent.UI.InventoryUI)
local RerollUI = require(script.Parent.UI.RerollUI)

local RollGacha = Remotes.Get("RollGacha")
local EquipPet = Remotes.Get("EquipPet")
local UnequipPet = Remotes.Get("UnequipPet")
local RerollRace = Remotes.Get("RerollRace")
local RerollTrait = Remotes.Get("RerollTrait")
local ProfileUpdated = Remotes.Get("ProfileUpdated")
local Notify = Remotes.Get("Notify")
local OpenReroll = Remotes.Get("OpenReroll")
local OpenGacha = Remotes.Get("OpenGacha")

local inventoryUI, gachaUI, rerollUI

local function showToast(text, kind)
	local color = Color3.fromRGB(255, 255, 255)
	if kind == "success" then
		color = Color3.fromRGB(120, 255, 120)
	elseif kind == "error" then
		color = Color3.fromRGB(255, 110, 110)
	end

	local label = Instance.new("TextLabel")
	label.Size = UDim2.new(0, 360, 0, 40)
	label.Position = UDim2.new(0.5, -180, 0.85, 0)
	label.BackgroundColor3 = Color3.fromRGB(20, 20, 30)
	label.BackgroundTransparency = 0.15
	label.Font = Enum.Font.GothamBold
	label.TextScaled = true
	label.TextColor3 = color
	label.Text = text
	label.Parent = screenGui
	Instance.new("UICorner", label).CornerRadius = UDim.new(0, 10)

	TweenService:Create(label, TweenInfo.new(2.5), { BackgroundTransparency = 1, TextTransparency = 1 }):Play()
	Debris:AddItem(label, 2.6)
end

local hud = HUD.new(screenGui, {
	onOpenInventory = function()
		inventoryUI:Toggle()
	end,
	onOpenGacha = function()
		gachaUI:Toggle()
	end,
})

gachaUI = GachaUI.new(screenGui, {
	onRoll = function()
		local result = RollGacha:InvokeServer()
		if result.success then
			gachaUI:ShowResult(result.pet)
		else
			gachaUI:ShowError(result.message)
		end
	end,
})

inventoryUI = InventoryUI.new(screenGui, {
	onEquip = function(uid)
		EquipPet:FireServer(uid)
	end,
	onUnequip = function(uid)
		UnequipPet:FireServer(uid)
	end,
})

rerollUI = RerollUI.new(screenGui, {
	onReroll = function(mode, uid)
		local remote = (mode == "raceReroll") and RerollRace or RerollTrait
		local result = remote:InvokeServer(uid)
		if result.success then
			showToast(("Rerolled into %s!"):format(mode == "raceReroll" and result.pet.race or result.pet.trait), "success")
		else
			showToast(result.message, "error")
		end
	end,
})

ProfileUpdated.OnClientEvent:Connect(function(profile)
	hud:UpdateProfile(profile)
	inventoryUI:UpdateProfile(profile)
	rerollUI:UpdateProfile(profile)
end)

Notify.OnClientEvent:Connect(function(text, kind)
	showToast(text, kind)
end)

OpenGacha.OnClientEvent:Connect(function()
	gachaUI:Show()
end)

OpenReroll.OnClientEvent:Connect(function(mode)
	rerollUI:SetMode(mode)
	rerollUI:Show()
end)
