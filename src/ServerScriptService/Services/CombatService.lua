local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Debris = game:GetService("Debris")

local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local NPCDatabase = require(ReplicatedStorage.Modules.NPCDatabase)
local Remotes = require(ReplicatedStorage.Modules.Remotes)

local DataService = require(script.Parent.DataService)
local PetService = require(script.Parent.PetService)

local CombatService = {}

local ProfileUpdated = Remotes.Get("ProfileUpdated")

local npcs = {} -- flat list of {part, zone, health, maxHealth, alive, healthFill}
local activePets = {} -- [userId] = { {uid=, part=, angle=, lastAttack=} , ... }
local petsFolder

local function fireProfileUpdated(player)
	local profile = DataService.Get(player)
	if profile then
		ProfileUpdated:FireClient(player, profile)
	end
end

local function popupText(part, text, color)
	local billboard = Instance.new("BillboardGui")
	billboard.Size = UDim2.new(4, 0, 1.5, 0)
	billboard.StudsOffset = Vector3.new(math.random(-2, 2), 2, 0)
	billboard.AlwaysOnTop = true
	billboard.Parent = part

	local label = Instance.new("TextLabel")
	label.Size = UDim2.new(1, 0, 1, 0)
	label.BackgroundTransparency = 1
	label.Font = Enum.Font.GothamBold
	label.TextScaled = true
	label.TextColor3 = color
	label.TextStrokeTransparency = 0.3
	label.Text = text
	label.Parent = billboard

	local tween = TweenService:Create(billboard, TweenInfo.new(0.8), {
		StudsOffset = billboard.StudsOffset + Vector3.new(0, 3, 0),
	})
	tween:Play()
	TweenService:Create(label, TweenInfo.new(0.8), { TextTransparency = 1 }):Play()
	Debris:AddItem(billboard, 0.85)
end

local function setNpcAlive(npc, alive)
	npc.alive = alive
	npc.part.Transparency = alive and 0 or 1
	npc.part.CanCollide = alive
	npc.healthBillboard.Enabled = alive
end

local function respawnNpc(npc)
	npc.health = npc.maxHealth
	npc.healthFill.Size = UDim2.new(1, 0, 1, 0)
	setNpcAlive(npc, true)
end

local function spawnNpcInstance(zone, index)
	local angle = math.random() * math.pi * 2
	local dist = math.random() * zone.radius
	local position = zone.origin + Vector3.new(math.cos(angle) * dist, 0, math.sin(angle) * dist)

	local part = Instance.new("Part")
	part.Name = zone.npcName .. "_" .. index
	part.Size = zone.npcSize
	part.Position = position
	part.Anchored = true
	part.CanCollide = true
	part.Color = zone.color
	part.Material = Enum.Material.SmoothPlastic
	part.Parent = workspace.GeneratedMap.CombatZones

	local billboard = Instance.new("BillboardGui")
	billboard.Name = "HealthBillboard"
	billboard.Size = UDim2.new(4, 0, 0.6, 0)
	billboard.StudsOffset = Vector3.new(0, zone.npcSize.Y / 2 + 1.5, 0)
	billboard.AlwaysOnTop = true
	billboard.Parent = part

	local nameLabel = Instance.new("TextLabel")
	nameLabel.Size = UDim2.new(1, 0, 0.5, 0)
	nameLabel.BackgroundTransparency = 1
	nameLabel.Font = Enum.Font.GothamBold
	nameLabel.TextScaled = true
	nameLabel.TextColor3 = Color3.new(1, 1, 1)
	nameLabel.TextStrokeTransparency = 0.4
	nameLabel.Text = zone.npcName
	nameLabel.Parent = billboard

	local barBack = Instance.new("Frame")
	barBack.Size = UDim2.new(1, 0, 0.5, 0)
	barBack.Position = UDim2.new(0, 0, 0.5, 0)
	barBack.BackgroundColor3 = Color3.fromRGB(40, 40, 40)
	barBack.BorderSizePixel = 0
	barBack.Parent = billboard

	local barFill = Instance.new("Frame")
	barFill.Size = UDim2.new(1, 0, 1, 0)
	barFill.BackgroundColor3 = Color3.fromRGB(220, 50, 50)
	barFill.BorderSizePixel = 0
	barFill.Parent = barBack

	return {
		part = part,
		zone = zone,
		health = zone.health,
		maxHealth = zone.health,
		alive = true,
		healthBillboard = billboard,
		healthFill = barFill,
	}
end

local function damageNpc(npc, amount, player, dropMult)
	if not npc.alive then
		return
	end

	npc.health = math.max(0, npc.health - amount)
	npc.healthFill.Size = UDim2.new(npc.health / npc.maxHealth, 0, 1, 0)
	popupText(npc.part, "-" .. math.floor(amount), Color3.fromRGB(255, 90, 90))

	local profile = DataService.Get(player)
	if profile then
		local cashGain = amount * npc.zone.cashPerDamage
		profile.Cash += cashGain
	end

	if npc.health <= 0 then
		setNpcAlive(npc, false)

		if profile then
			profile.Cash += npc.zone.killBonus
			if math.random() <= npc.zone.dropChance * dropMult then
				profile.Gems += npc.zone.gemsOnDrop
				popupText(npc.part, "+" .. npc.zone.gemsOnDrop .. " gems!", Color3.fromRGB(120, 220, 255))
			end
		end

		task.delay(npc.zone.respawnTime, respawnNpc, npc)
	end

	if profile then
		fireProfileUpdated(player)
	end
end

local function findNearestAliveNpc(position)
	local nearest, nearestDist
	for _, npc in ipairs(npcs) do
		if npc.alive then
			local dist = (npc.part.Position - position).Magnitude
			if dist <= GameConfig.AttackRange and (not nearestDist or dist < nearestDist) then
				nearest = npc
				nearestDist = dist
			end
		end
	end
	return nearest
end

function CombatService.SyncPets(player)
	local profile = DataService.Get(player)
	if not profile then
		return
	end

	local userId = player.UserId
	local existing = activePets[userId] or {}
	local existingByUid = {}
	for _, entry in ipairs(existing) do
		existingByUid[entry.uid] = entry
	end

	local newList = {}
	for i, uid in ipairs(profile.EquippedPetUids) do
		local entry = existingByUid[uid]
		if entry then
			existingByUid[uid] = nil
		else
			local pet = PetService.FindPet(profile, uid)
			if pet then
				local stats = PetService.GetEffectiveStats(profile, pet)
				local part = Instance.new("Part")
				part.Name = "Pet_" .. stats.species.name
				part.Shape = Enum.PartType.Ball
				part.Size = Vector3.new(2.5, 2.5, 2.5)
				part.Color = stats.race.color
				part.Material = Enum.Material.Neon
				part.Anchored = true
				part.CanCollide = false
				part.Parent = petsFolder

				entry = { uid = uid, part = part, lastAttack = 0 }
			end
		end

		if entry then
			entry.angle = (i - 1) * (math.pi * 2 / math.max(1, #profile.EquippedPetUids))
			table.insert(newList, entry)
		end
	end

	for _, leftover in pairs(existingByUid) do
		if leftover.part then
			leftover.part:Destroy()
		end
	end

	activePets[userId] = newList
end

function CombatService.CleanupPlayer(player)
	local userId = player.UserId
	local list = activePets[userId]
	if list then
		for _, entry in ipairs(list) do
			if entry.part then
				entry.part:Destroy()
			end
		end
	end
	activePets[userId] = nil
end

local function updatePlayerPets(player, now)
	local character = player.Character
	if not character then
		return
	end

	local rootPart = character:FindFirstChild("HumanoidRootPart")
	if not rootPart then
		return
	end

	local profile = DataService.Get(player)
	if not profile then
		return
	end

	local list = activePets[player.UserId]
	if not list then
		return
	end

	for _, entry in ipairs(list) do
		local pet = PetService.FindPet(profile, entry.uid)
		if pet and entry.part then
			local orbitAngle = now * 1.5 + entry.angle
			local offset = Vector3.new(math.cos(orbitAngle) * 4, 2 + math.sin(now * 3 + entry.angle), math.sin(orbitAngle) * 4)
			entry.part.Position = rootPart.Position + offset

			local stats = PetService.GetEffectiveStats(profile, pet)
			if now - entry.lastAttack >= stats.attackInterval then
				local target = findNearestAliveNpc(rootPart.Position)
				if target then
					entry.lastAttack = now
					damageNpc(target, stats.damage, player, stats.dropMult)
				end
			end
		end
	end
end

function CombatService.Init()
	petsFolder = Instance.new("Folder")
	petsFolder.Name = "Pets"
	petsFolder.Parent = workspace

	for _, zone in ipairs(NPCDatabase) do
		for i = 1, zone.count do
			table.insert(npcs, spawnNpcInstance(zone, i))
		end
	end

	RunService.Heartbeat:Connect(function()
		local now = os.clock()
		for _, player in ipairs(Players:GetPlayers()) do
			updatePlayerPets(player, now)
		end
	end)
end

return CombatService
