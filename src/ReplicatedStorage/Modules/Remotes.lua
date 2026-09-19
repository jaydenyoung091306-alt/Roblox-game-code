local ReplicatedStorage = game:GetService("ReplicatedStorage")

local REMOTE_EVENTS = {
	"EquipPet",
	"UnequipPet",
	"ProfileUpdated",
	"Notify",
	"OpenReroll",
	"OpenGacha",
}

local REMOTE_FUNCTIONS = {
	"RollGacha",
	"RerollRace",
	"RerollTrait",
}

local Remotes = {}

function Remotes.CreateAll()
	local folder = ReplicatedStorage:FindFirstChild("Remotes")
	if not folder then
		folder = Instance.new("Folder")
		folder.Name = "Remotes"
		folder.Parent = ReplicatedStorage
	end

	for _, name in ipairs(REMOTE_EVENTS) do
		if not folder:FindFirstChild(name) then
			local remote = Instance.new("RemoteEvent")
			remote.Name = name
			remote.Parent = folder
		end
	end

	for _, name in ipairs(REMOTE_FUNCTIONS) do
		if not folder:FindFirstChild(name) then
			local remote = Instance.new("RemoteFunction")
			remote.Name = name
			remote.Parent = folder
		end
	end

	return folder
end

function Remotes.Get(name)
	local folder = ReplicatedStorage:WaitForChild("Remotes", 10)
	if not folder then
		error("Remotes folder was never created by the server")
	end
	return folder:WaitForChild(name)
end

return Remotes
