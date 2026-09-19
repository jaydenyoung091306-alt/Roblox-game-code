local ReplicatedStorage = game:GetService("ReplicatedStorage")
local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local PetDatabase = require(ReplicatedStorage.Modules.PetDatabase)
local Util = require(ReplicatedStorage.Modules.Util)

local InventoryUI = {}
InventoryUI.__index = InventoryUI

local function rarityColor(rarityName)
	local rarity = Util.FindByField(GameConfig.Rarities, "name", rarityName)
	return rarity and rarity.color or Color3.new(1, 1, 1)
end

function InventoryUI.new(screenGui, callbacks)
	local self = setmetatable({}, InventoryUI)
	self.callbacks = callbacks

	local frame = Instance.new("Frame")
	frame.Name = "InventoryFrame"
	frame.Size = UDim2.new(0, 420, 0, 460)
	frame.Position = UDim2.new(0.5, -210, 0.5, -230)
	frame.BackgroundColor3 = Color3.fromRGB(25, 25, 35)
	frame.Visible = false
	frame.Parent = screenGui
	Instance.new("UICorner", frame).CornerRadius = UDim.new(0, 14)

	local title = Instance.new("TextLabel")
	title.Name = "Title"
	title.Size = UDim2.new(1, 0, 0, 40)
	title.BackgroundTransparency = 1
	title.Font = Enum.Font.GothamBlack
	title.TextScaled = true
	title.TextColor3 = Color3.new(1, 1, 1)
	title.Text = "Pets (0/0)"
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

	local scroll = Instance.new("ScrollingFrame")
	scroll.Size = UDim2.new(1, -20, 1, -55)
	scroll.Position = UDim2.new(0, 10, 0, 48)
	scroll.BackgroundTransparency = 1
	scroll.ScrollBarThickness = 6
	scroll.CanvasSize = UDim2.new(0, 0, 0, 0)
	scroll.AutomaticCanvasSize = Enum.AutomaticSize.Y
	scroll.Parent = frame

	local layout = Instance.new("UIListLayout")
	layout.Padding = UDim.new(0, 6)
	layout.Parent = scroll

	self.frame = frame
	self.title = title
	self.scroll = scroll

	return self
end

function InventoryUI:UpdateProfile(profile)
	self.title.Text = ("Pets (%d/%d)"):format(#profile.EquippedPetUids, profile.MaxPetSlots)

	for _, child in ipairs(self.scroll:GetChildren()) do
		if child:IsA("Frame") then
			child:Destroy()
		end
	end

	local equippedSet = {}
	for _, uid in ipairs(profile.EquippedPetUids) do
		equippedSet[uid] = true
	end

	for i, pet in ipairs(profile.Pets) do
		local species = Util.FindByField(PetDatabase, "id", pet.speciesId)
		local isEquipped = equippedSet[pet.uid] == true

		local row = Instance.new("Frame")
		row.Name = "Row_" .. i
		row.Size = UDim2.new(1, 0, 0, 56)
		row.BackgroundColor3 = Color3.fromRGB(40, 40, 55)
		row.LayoutOrder = i
		row.Parent = self.scroll
		Instance.new("UICorner", row).CornerRadius = UDim.new(0, 8)

		local info = Instance.new("TextLabel")
		info.Size = UDim2.new(1, -110, 1, 0)
		info.Position = UDim2.new(0, 10, 0, 0)
		info.BackgroundTransparency = 1
		info.Font = Enum.Font.GothamBold
		info.TextScaled = true
		info.TextXAlignment = Enum.TextXAlignment.Left
		info.TextColor3 = rarityColor(pet.rarity)
		info.Text = ("%s %s [%s]\n%s - %s"):format(pet.race, species.name, pet.rarity, pet.trait, isEquipped and "Equipped" or "Stored")
		info.Parent = row

		local actionButton = Instance.new("TextButton")
		actionButton.Size = UDim2.new(0, 90, 0, 40)
		actionButton.Position = UDim2.new(1, -100, 0.5, -20)
		actionButton.Font = Enum.Font.GothamBold
		actionButton.TextScaled = true
		actionButton.TextColor3 = Color3.new(1, 1, 1)
		actionButton.Parent = row
		Instance.new("UICorner", actionButton).CornerRadius = UDim.new(0, 8)

		if isEquipped then
			actionButton.Text = "Unequip"
			actionButton.BackgroundColor3 = Color3.fromRGB(200, 90, 60)
			actionButton.MouseButton1Click:Connect(function()
				if self.callbacks.onUnequip then
					self.callbacks.onUnequip(pet.uid)
				end
			end)
		else
			actionButton.Text = "Equip"
			actionButton.BackgroundColor3 = Color3.fromRGB(70, 180, 90)
			actionButton.MouseButton1Click:Connect(function()
				if self.callbacks.onEquip then
					self.callbacks.onEquip(pet.uid)
				end
			end)
		end
	end
end

function InventoryUI:Show()
	self.frame.Visible = true
end

function InventoryUI:Hide()
	self.frame.Visible = false
end

function InventoryUI:Toggle()
	self.frame.Visible = not self.frame.Visible
end

return InventoryUI
