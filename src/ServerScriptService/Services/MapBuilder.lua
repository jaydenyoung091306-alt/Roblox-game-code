local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local NPCDatabase = require(ReplicatedStorage.Modules.NPCDatabase)
local Remotes = require(ReplicatedStorage.Modules.Remotes)

local MapBuilder = {}

local function makePart(props)
	local part = Instance.new("Part")
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	for key, value in pairs(props) do
		part[key] = value
	end
	return part
end

local function makeBillboardButton(part, title)
	local billboard = Instance.new("BillboardGui")
	billboard.Name = "Billboard"
	billboard.Size = UDim2.new(6, 0, 2, 0)
	billboard.StudsOffset = Vector3.new(0, 2, 0)
	billboard.AlwaysOnTop = true
	billboard.Parent = part

	local titleLabel = Instance.new("TextLabel")
	titleLabel.Name = "TitleLabel"
	titleLabel.Size = UDim2.new(1, 0, 0.5, 0)
	titleLabel.BackgroundTransparency = 1
	titleLabel.TextScaled = true
	titleLabel.Font = Enum.Font.GothamBold
	titleLabel.TextColor3 = Color3.new(1, 1, 1)
	titleLabel.TextStrokeTransparency = 0.4
	titleLabel.Text = title
	titleLabel.Parent = billboard

	local priceLabel = Instance.new("TextLabel")
	priceLabel.Name = "PriceLabel"
	priceLabel.Size = UDim2.new(1, 0, 0.5, 0)
	priceLabel.Position = UDim2.new(0, 0, 0.5, 0)
	priceLabel.BackgroundTransparency = 1
	priceLabel.TextScaled = true
	priceLabel.Font = Enum.Font.GothamBold
	priceLabel.TextColor3 = Color3.fromRGB(255, 240, 150)
	priceLabel.TextStrokeTransparency = 0.4
	priceLabel.Text = ""
	priceLabel.Parent = billboard

	local clickDetector = Instance.new("ClickDetector")
	clickDetector.MaxActivationDistance = 16
	clickDetector.Parent = part

	return billboard, clickDetector
end

local function buildPlot(index, foldersParent)
	local col = (index - 1) % 3
	local row = math.floor((index - 1) / 3)
	local originX = col * GameConfig.PlotSpacing
	local originZ = -(row * GameConfig.PlotSpacing) - 40

	local model = Instance.new("Model")
	model.Name = "Plot_" .. index
	model.Parent = foldersParent

	local base = makePart({
		Name = "Base",
		Size = GameConfig.PlotSize,
		Position = Vector3.new(originX, 0.5, originZ),
		Color = Color3.fromRGB(120, 170, 120),
		Material = Enum.Material.Grass,
		Parent = model,
	})

	local spawnPart = makePart({
		Name = "SpawnPoint",
		Size = Vector3.new(4, 1, 4),
		Position = Vector3.new(originX, 1.5, originZ + 18),
		Color = Color3.fromRGB(90, 140, 220),
		Transparency = 0.4,
		CanCollide = false,
		Parent = model,
	})

	local ownerLabelPart = makePart({
		Name = "OwnerSign",
		Size = Vector3.new(1, 1, 1),
		Position = Vector3.new(originX, 8, originZ + 20),
		Transparency = 1,
		CanCollide = false,
		Parent = model,
	})
	local ownerBillboard = Instance.new("BillboardGui")
	ownerBillboard.Size = UDim2.new(10, 0, 2, 0)
	ownerBillboard.StudsOffset = Vector3.new(0, 0, 0)
	ownerBillboard.AlwaysOnTop = true
	ownerBillboard.Parent = ownerLabelPart
	local ownerLabel = Instance.new("TextLabel")
	ownerLabel.Size = UDim2.new(1, 0, 1, 0)
	ownerLabel.BackgroundTransparency = 1
	ownerLabel.TextScaled = true
	ownerLabel.Font = Enum.Font.GothamBold
	ownerLabel.TextColor3 = Color3.new(1, 1, 1)
	ownerLabel.TextStrokeTransparency = 0.2
	ownerLabel.Text = "Unclaimed"
	ownerLabel.Parent = ownerBillboard

	local buttons = {}
	for i, upgrade in ipairs(GameConfig.TycoonUpgrades) do
		local bx = originX - 18 + ((i - 1) % 6) * 7
		local bz = originZ - 18 + math.floor((i - 1) / 6) * 7

		local buttonPart = makePart({
			Name = "Button_" .. upgrade.id,
			Size = Vector3.new(4, 3, 4),
			Position = Vector3.new(bx, 2, bz),
			Color = Color3.fromRGB(150, 150, 150),
			Material = Enum.Material.Neon,
			Parent = model,
		})

		local billboard, clickDetector = makeBillboardButton(buttonPart, upgrade.name)

		buttons[upgrade.id] = {
			part = buttonPart,
			billboard = billboard,
			clickDetector = clickDetector,
		}
	end

	local raceRerollPart = makePart({
		Name = "RaceRerollMachine",
		Size = Vector3.new(5, 6, 5),
		Position = Vector3.new(originX + 16, 3, originZ - 18),
		Color = Color3.fromRGB(255, 100, 220),
		Material = Enum.Material.Neon,
		CanCollide = false,
		Transparency = 0.85,
		Parent = model,
	})
	makeBillboardButton(raceRerollPart, "Race Reroll")
	local raceClickDetector = raceRerollPart:FindFirstChildOfClass("ClickDetector")
	raceClickDetector.MaxActivationDistance = 16

	local traitRerollPart = makePart({
		Name = "TraitRerollMachine",
		Size = Vector3.new(5, 6, 5),
		Position = Vector3.new(originX - 16, 3, originZ - 18),
		Color = Color3.fromRGB(100, 220, 255),
		Material = Enum.Material.Neon,
		CanCollide = false,
		Transparency = 0.85,
		Parent = model,
	})
	makeBillboardButton(traitRerollPart, "Trait Reroll")
	local traitClickDetector = traitRerollPart:FindFirstChildOfClass("ClickDetector")
	traitClickDetector.MaxActivationDistance = 16

	return {
		id = index,
		model = model,
		spawnPart = spawnPart,
		buttons = buttons,
		raceRerollPart = raceRerollPart,
		traitRerollPart = traitRerollPart,
		ownerLabel = ownerLabel,
	}
end

local function buildCombatZones(parent)
	for _, zone in ipairs(NPCDatabase) do
		local ground = makePart({
			Name = "Zone_" .. zone.id,
			Size = Vector3.new(zone.radius * 2.4, 1, zone.radius * 2.4),
			Position = Vector3.new(zone.origin.X, zone.origin.Y - 2.5, zone.origin.Z),
			Color = zone.color,
			Material = Enum.Material.Ground,
			Parent = parent,
		})

		local signPart = makePart({
			Name = "Zone_" .. zone.id .. "_Sign",
			Size = Vector3.new(1, 1, 1),
			Position = zone.origin + Vector3.new(0, 14, 0),
			Transparency = 1,
			CanCollide = false,
			Parent = parent,
		})
		local billboard = Instance.new("BillboardGui")
		billboard.Size = UDim2.new(14, 0, 3, 0)
		billboard.AlwaysOnTop = true
		billboard.Parent = signPart
		local label = Instance.new("TextLabel")
		label.Size = UDim2.new(1, 0, 1, 0)
		label.BackgroundTransparency = 1
		label.TextScaled = true
		label.Font = Enum.Font.GothamBlack
		label.TextColor3 = Color3.new(1, 1, 1)
		label.TextStrokeTransparency = 0
		label.Text = zone.zoneName
		label.Parent = billboard

		ground.Parent = parent
	end
end

function MapBuilder.Build()
	Remotes.CreateAll()

	local mapFolder = Instance.new("Folder")
	mapFolder.Name = "GeneratedMap"
	mapFolder.Parent = workspace

	makePart({
		Name = "Baseplate",
		Size = Vector3.new(600, 2, 600),
		Position = Vector3.new(120, -1, -20),
		Color = Color3.fromRGB(90, 130, 90),
		Material = Enum.Material.Grass,
		Parent = mapFolder,
	})

	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "MainSpawn"
	spawn.Size = Vector3.new(10, 1, 10)
	spawn.Position = Vector3.new(200, 0.5, 30)
	spawn.Anchored = true
	spawn.Neutral = true
	spawn.TopSurface = Enum.SurfaceType.Smooth
	spawn.Duplicate = false
	spawn.Parent = mapFolder

	local gachaPart = makePart({
		Name = "GachaMachine",
		Size = Vector3.new(8, 10, 8),
		Position = Vector3.new(200, 5, 60),
		Color = Color3.fromRGB(255, 60, 200),
		Material = Enum.Material.Neon,
		Parent = mapFolder,
	})
	local gachaBillboard, gachaClickDetector = makeBillboardButton(gachaPart, "Gacha")
	gachaBillboard.PriceLabel.Text = ("$%d / roll"):format(GameConfig.GachaCashCost)
	gachaClickDetector.MaxActivationDistance = 20

	local OpenGacha = Remotes.Get("OpenGacha")
	gachaClickDetector.MouseClick:Connect(function(player)
		OpenGacha:FireClient(player)
	end)

	local plotsFolder = Instance.new("Folder")
	plotsFolder.Name = "Plots"
	plotsFolder.Parent = mapFolder

	local plots = {}
	for i = 1, GameConfig.PlotCount do
		table.insert(plots, buildPlot(i, plotsFolder))
	end

	local combatFolder = Instance.new("Folder")
	combatFolder.Name = "CombatZones"
	combatFolder.Parent = mapFolder
	buildCombatZones(combatFolder)

	return {
		plots = plots,
		mapFolder = mapFolder,
	}
end

return MapBuilder
