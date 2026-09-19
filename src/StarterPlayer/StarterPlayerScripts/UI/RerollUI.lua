local ReplicatedStorage = game:GetService("ReplicatedStorage")
local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local PetDatabase = require(ReplicatedStorage.Modules.PetDatabase)
local Util = require(ReplicatedStorage.Modules.Util)

local RerollUI = {}
RerollUI.__index = RerollUI

function RerollUI.new(screenGui, callbacks)
	local self = setmetatable({}, RerollUI)
	self.callbacks = callbacks
	self.mode = "raceReroll"
	self.profile = nil

	local frame = Instance.new("Frame")
	frame.Name = "RerollFrame"
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
	title.Text = "Reroll"
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

function RerollUI:SetMode(mode)
	self.mode = mode
	self.title.Text = (mode == "raceReroll") and ("Race Reroll (" .. GameConfig.RaceRerollGemCost .. " gems)")
		or ("Trait Reroll (" .. GameConfig.TraitRerollGemCost .. " gems)")
	self:Refresh()
end

function RerollUI:UpdateProfile(profile)
	self.profile = profile
	self:Refresh()
end

function RerollUI:Refresh()
	for _, child in ipairs(self.scroll:GetChildren()) do
		if child:IsA("Frame") then
			child:Destroy()
		end
	end

	if not self.profile then
		return
	end

	for i, pet in ipairs(self.profile.Pets) do
		local species = Util.FindByField(PetDatabase, "id", pet.speciesId)

		local row = Instance.new("Frame")
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
		info.TextColor3 = Color3.new(1, 1, 1)
		info.Text = ("%s %s [%s]\nRace: %s | Trait: %s"):format(pet.race, species.name, pet.rarity, pet.race, pet.trait)
		info.Parent = row

		local rerollButton = Instance.new("TextButton")
		rerollButton.Size = UDim2.new(0, 90, 0, 40)
		rerollButton.Position = UDim2.new(1, -100, 0.5, -20)
		rerollButton.BackgroundColor3 = Color3.fromRGB(200, 120, 220)
		rerollButton.Font = Enum.Font.GothamBold
		rerollButton.TextScaled = true
		rerollButton.TextColor3 = Color3.new(1, 1, 1)
		rerollButton.Text = "Reroll"
		rerollButton.Parent = row
		Instance.new("UICorner", rerollButton).CornerRadius = UDim.new(0, 8)

		rerollButton.MouseButton1Click:Connect(function()
			if self.callbacks.onReroll then
				self.callbacks.onReroll(self.mode, pet.uid)
			end
		end)
	end
end

function RerollUI:Show()
	self.frame.Visible = true
end

function RerollUI:Hide()
	self.frame.Visible = false
end

return RerollUI
