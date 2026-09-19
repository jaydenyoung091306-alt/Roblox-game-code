local Util = require(game:GetService("ReplicatedStorage").Modules.Util)

local HUD = {}
HUD.__index = HUD

function HUD.new(screenGui, callbacks)
	local self = setmetatable({}, HUD)

	local topBar = Instance.new("Frame")
	topBar.Name = "TopBar"
	topBar.Size = UDim2.new(0, 260, 0, 90)
	topBar.Position = UDim2.new(0, 12, 0, 12)
	topBar.BackgroundColor3 = Color3.fromRGB(25, 25, 35)
	topBar.BackgroundTransparency = 0.2
	topBar.Parent = screenGui

	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(0, 12)
	corner.Parent = topBar

	local cashLabel = Instance.new("TextLabel")
	cashLabel.Size = UDim2.new(1, -20, 0, 35)
	cashLabel.Position = UDim2.new(0, 10, 0, 5)
	cashLabel.BackgroundTransparency = 1
	cashLabel.Font = Enum.Font.GothamBold
	cashLabel.TextScaled = true
	cashLabel.TextXAlignment = Enum.TextXAlignment.Left
	cashLabel.TextColor3 = Color3.fromRGB(120, 255, 120)
	cashLabel.Text = "$0"
	cashLabel.Parent = topBar

	local gemsLabel = Instance.new("TextLabel")
	gemsLabel.Size = UDim2.new(1, -20, 0, 35)
	gemsLabel.Position = UDim2.new(0, 10, 0, 42)
	gemsLabel.BackgroundTransparency = 1
	gemsLabel.Font = Enum.Font.GothamBold
	gemsLabel.TextScaled = true
	gemsLabel.TextXAlignment = Enum.TextXAlignment.Left
	gemsLabel.TextColor3 = Color3.fromRGB(120, 220, 255)
	gemsLabel.Text = "0 Gems"
	gemsLabel.Parent = topBar

	local buttonHolder = Instance.new("Frame")
	buttonHolder.Name = "Buttons"
	buttonHolder.Size = UDim2.new(0, 160, 0, 50)
	buttonHolder.Position = UDim2.new(0, 12, 0, 110)
	buttonHolder.BackgroundTransparency = 1
	buttonHolder.Parent = screenGui

	local layout = Instance.new("UIListLayout")
	layout.FillDirection = Enum.FillDirection.Vertical
	layout.Padding = UDim.new(0, 8)
	layout.Parent = buttonHolder

	local function makeButton(text, order, callback)
		local button = Instance.new("TextButton")
		button.Size = UDim2.new(1, 0, 0, 42)
		button.BackgroundColor3 = Color3.fromRGB(45, 45, 60)
		button.Font = Enum.Font.GothamBold
		button.TextScaled = true
		button.TextColor3 = Color3.new(1, 1, 1)
		button.Text = text
		button.LayoutOrder = order
		button.Parent = buttonHolder

		local btnCorner = Instance.new("UICorner")
		btnCorner.CornerRadius = UDim.new(0, 8)
		btnCorner.Parent = button

		button.MouseButton1Click:Connect(callback)
		return button
	end

	makeButton("Pets", 1, function()
		if callbacks.onOpenInventory then
			callbacks.onOpenInventory()
		end
	end)

	makeButton("Gacha", 2, function()
		if callbacks.onOpenGacha then
			callbacks.onOpenGacha()
		end
	end)

	self.cashLabel = cashLabel
	self.gemsLabel = gemsLabel

	return self
end

function HUD:UpdateProfile(profile)
	self.cashLabel.Text = "$" .. Util.FormatNumber(profile.Cash)
	self.gemsLabel.Text = Util.FormatNumber(profile.Gems) .. " Gems"
end

return HUD
