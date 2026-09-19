local ReplicatedStorage = game:GetService("ReplicatedStorage")
local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local PetDatabase = require(ReplicatedStorage.Modules.PetDatabase)
local Util = require(ReplicatedStorage.Modules.Util)

local GachaUI = {}
GachaUI.__index = GachaUI

local function rarityColor(rarityName)
	local rarity = Util.FindByField(GameConfig.Rarities, "name", rarityName)
	return rarity and rarity.color or Color3.new(1, 1, 1)
end

function GachaUI.new(screenGui, callbacks)
	local self = setmetatable({}, GachaUI)

	local frame = Instance.new("Frame")
	frame.Name = "GachaFrame"
	frame.Size = UDim2.new(0, 340, 0, 280)
	frame.Position = UDim2.new(0.5, -170, 0.5, -140)
	frame.BackgroundColor3 = Color3.fromRGB(25, 25, 35)
	frame.Visible = false
	frame.Parent = screenGui

	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(0, 14)
	corner.Parent = frame

	local title = Instance.new("TextLabel")
	title.Size = UDim2.new(1, 0, 0, 40)
	title.BackgroundTransparency = 1
	title.Font = Enum.Font.GothamBlack
	title.TextScaled = true
	title.TextColor3 = Color3.new(1, 1, 1)
	title.Text = "Pet Gacha"
	title.Parent = frame

	local closeButton = Instance.new("TextButton")
	closeButton.Size = UDim2.new(0, 32, 0, 32)
	closeButton.Position = UDim2.new(1, -40, 0, 6)
	closeButton.BackgroundColor3 = Color3.fromRGB(200, 60, 60)
	closeButton.Font = Enum.Font.GothamBold
	closeButton.TextScaled = true
	closeButton.TextColor3 = Color3.new(1, 1, 1)
	closeButton.Text = "X"
	closeButton.Parent = frame
	Instance.new("UICorner", closeButton).CornerRadius = UDim.new(0, 8)
	closeButton.MouseButton1Click:Connect(function()
		self:Hide()
	end)

	local resultLabel = Instance.new("TextLabel")
	resultLabel.Size = UDim2.new(1, -30, 0, 130)
	resultLabel.Position = UDim2.new(0, 15, 0, 50)
	resultLabel.BackgroundColor3 = Color3.fromRGB(40, 40, 55)
	resultLabel.Font = Enum.Font.GothamBold
	resultLabel.TextScaled = true
	resultLabel.TextWrapped = true
	resultLabel.TextColor3 = Color3.new(1, 1, 1)
	resultLabel.Text = "Roll to get a pet!"
	resultLabel.Parent = frame
	Instance.new("UICorner", resultLabel).CornerRadius = UDim.new(0, 10)

	local rollButton = Instance.new("TextButton")
	rollButton.Size = UDim2.new(1, -30, 0, 50)
	rollButton.Position = UDim2.new(0, 15, 1, -65)
	rollButton.BackgroundColor3 = Color3.fromRGB(70, 200, 90)
	rollButton.Font = Enum.Font.GothamBlack
	rollButton.TextScaled = true
	rollButton.TextColor3 = Color3.new(1, 1, 1)
	rollButton.Text = ("Roll ($%d)"):format(GameConfig.GachaCashCost)
	rollButton.Parent = frame
	Instance.new("UICorner", rollButton).CornerRadius = UDim.new(0, 10)

	rollButton.MouseButton1Click:Connect(function()
		if callbacks.onRoll then
			callbacks.onRoll()
		end
	end)

	self.frame = frame
	self.resultLabel = resultLabel

	return self
end

function GachaUI:ShowResult(pet)
	local species = Util.FindByField(PetDatabase, "id", pet.speciesId)
	self.resultLabel.TextColor3 = rarityColor(pet.rarity)
	self.resultLabel.Text = ("You got a %s %s %s!\n[%s]"):format(pet.race, species.name, pet.trait, pet.rarity)
end

function GachaUI:ShowError(message)
	self.resultLabel.TextColor3 = Color3.fromRGB(255, 100, 100)
	self.resultLabel.Text = message
end

function GachaUI:Show()
	self.frame.Visible = true
end

function GachaUI:Hide()
	self.frame.Visible = false
end

function GachaUI:Toggle()
	self.frame.Visible = not self.frame.Visible
end

return GachaUI
