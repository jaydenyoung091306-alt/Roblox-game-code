local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local Util = require(ReplicatedStorage.Modules.Util)
local Remotes = require(ReplicatedStorage.Modules.Remotes)

local DataService = require(script.Parent.DataService)

local TycoonService = {}

local plotsById = {}
local ownerByPlotId = {}
local plotIdByUserId = {}

local ProfileUpdated = Remotes.Get("ProfileUpdated")
local Notify = Remotes.Get("Notify")
local OpenReroll = Remotes.Get("OpenReroll")

local function fireProfileUpdated(player)
	local profile = DataService.Get(player)
	if profile then
		ProfileUpdated:FireClient(player, profile)
	end
end

local function notify(player, text, kind)
	Notify:FireClient(player, text, kind or "info")
end

local function refreshPlotVisuals(plot)
	local profile
	local ownerUserId = ownerByPlotId[plot.id]
	if ownerUserId then
		local ownerPlayer = Players:GetPlayerByUserId(ownerUserId)
		if ownerPlayer then
			profile = DataService.Get(ownerPlayer)
		end
	end

	for upgradeId, button in pairs(plot.buttons) do
		local upgrade = Util.FindByField(GameConfig.TycoonUpgrades, "id", upgradeId)
		local label = button.billboard.PriceLabel
		local titleLabel = button.billboard.TitleLabel

		titleLabel.Text = upgrade.name

		if profile and profile.Upgrades[upgradeId] then
			label.Text = "OWNED"
			button.part.Color = Color3.fromRGB(70, 200, 90)
		elseif profile then
			label.Text = "$" .. Util.FormatNumber(upgrade.cost)
			button.part.Color = Color3.fromRGB(230, 200, 60)
		else
			label.Text = "$" .. Util.FormatNumber(upgrade.cost)
			button.part.Color = Color3.fromRGB(150, 150, 150)
		end
	end

	if plot.raceRerollPart then
		plot.raceRerollPart.Transparency = (profile and profile.Upgrades["racereroll"]) and 0 or 0.85
		plot.raceRerollPart.CanCollide = (profile and profile.Upgrades["racereroll"]) and true or false
	end

	if plot.traitRerollPart then
		plot.traitRerollPart.Transparency = (profile and profile.Upgrades["traitreroll"]) and 0 or 0.85
		plot.traitRerollPart.CanCollide = (profile and profile.Upgrades["traitreroll"]) and true or false
	end

	if plot.ownerLabel then
		local ownerPlayer = ownerUserId and Players:GetPlayerByUserId(ownerUserId)
		plot.ownerLabel.Text = ownerPlayer and (ownerPlayer.Name .. "'s Base") or "Unclaimed"
	end
end

function TycoonService.PurchaseUpgrade(player, upgradeId)
	local profile = DataService.Get(player)
	if not profile then
		return false, "Data not loaded yet"
	end

	local plotId = plotIdByUserId[player.UserId]
	if not plotId then
		return false, "You do not own a base yet"
	end

	if profile.Upgrades[upgradeId] then
		return false, "Already owned"
	end

	local upgrade = Util.FindByField(GameConfig.TycoonUpgrades, "id", upgradeId)
	if not upgrade then
		return false, "Unknown upgrade"
	end

	if profile.Cash < upgrade.cost then
		return false, "Not enough cash"
	end

	profile.Cash -= upgrade.cost
	profile.Upgrades[upgradeId] = true

	if upgrade.effect.type == "petSlot" then
		profile.MaxPetSlots = math.max(profile.MaxPetSlots, upgrade.effect.value)
	end

	refreshPlotVisuals(plotsById[plotId])
	fireProfileUpdated(player)
	notify(player, ("Purchased %s!"):format(upgrade.name), "success")

	return true
end

local function teleportToPlot(player, plot)
	local character = player.Character or player.CharacterAdded:Wait()
	local rootPart = character:WaitForChild("HumanoidRootPart", 5)
	if rootPart and plot.spawnPart then
		rootPart.CFrame = plot.spawnPart.CFrame + Vector3.new(0, 5, 0)
	end
end

function TycoonService.AssignPlot(player)
	local profile = DataService.Get(player)
	if not profile then
		return
	end

	for _, plot in pairs(plotsById) do
		if not ownerByPlotId[plot.id] then
			ownerByPlotId[plot.id] = player.UserId
			plotIdByUserId[player.UserId] = plot.id
			profile.PlotId = plot.id

			refreshPlotVisuals(plot)
			teleportToPlot(player, plot)
			return plot
		end
	end

	notify(player, "All bases are full right now, try again later!", "error")
	return nil
end

function TycoonService.ReleasePlot(player)
	local plotId = plotIdByUserId[player.UserId]
	if not plotId then
		return
	end

	ownerByPlotId[plotId] = nil
	plotIdByUserId[player.UserId] = nil

	local plot = plotsById[plotId]
	if plot then
		refreshPlotVisuals(plot)
	end
end

local function onButtonClicked(player, plot, upgradeId)
	local plotId = plotIdByUserId[player.UserId]
	if plotId ~= plot.id then
		notify(player, "This is not your base!", "error")
		return
	end

	local success, err = TycoonService.PurchaseUpgrade(player, upgradeId)
	if not success then
		notify(player, err, "error")
	end
end

local function onRerollPartClicked(player, plot, rerollType)
	local plotId = plotIdByUserId[player.UserId]
	if plotId ~= plot.id then
		notify(player, "This is not your base!", "error")
		return
	end

	OpenReroll:FireClient(player, rerollType)
end

function TycoonService.Init(plots)
	for _, plot in ipairs(plots) do
		plotsById[plot.id] = plot

		for upgradeId, button in pairs(plot.buttons) do
			button.clickDetector.MouseClick:Connect(function(player)
				onButtonClicked(player, plot, upgradeId)
			end)
		end

		if plot.raceRerollPart then
			local clickDetector = plot.raceRerollPart:FindFirstChildOfClass("ClickDetector")
			if clickDetector then
				clickDetector.MouseClick:Connect(function(player)
					onRerollPartClicked(player, plot, "raceReroll")
				end)
			end
		end

		if plot.traitRerollPart then
			local clickDetector = plot.traitRerollPart:FindFirstChildOfClass("ClickDetector")
			if clickDetector then
				clickDetector.MouseClick:Connect(function(player)
					onRerollPartClicked(player, plot, "traitReroll")
				end)
			end
		end

		refreshPlotVisuals(plot)
	end

	task.spawn(function()
		while true do
			task.wait(GameConfig.PassiveIncomeInterval)
			for userId, plotId in pairs(plotIdByUserId) do
				local player = Players:GetPlayerByUserId(userId)
				local profile = player and DataService.Get(player)
				if profile then
					local income = 0
					for _, upgrade in ipairs(GameConfig.TycoonUpgrades) do
						if upgrade.effect.type == "passiveIncome" and profile.Upgrades[upgrade.id] then
							income += upgrade.effect.value
						end
					end
					if income > 0 then
						profile.Cash += income
						fireProfileUpdated(player)
					end
				end
			end
		end
	end)
end

return TycoonService
