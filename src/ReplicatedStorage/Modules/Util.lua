local Util = {}

function Util.WeightedPick(entries)
	local total = 0
	for _, entry in ipairs(entries) do
		total += entry.weight
	end

	local roll = math.random() * total
	local cursor = 0
	for _, entry in ipairs(entries) do
		cursor += entry.weight
		if roll <= cursor then
			return entry
		end
	end

	return entries[#entries]
end

function Util.FindByField(list, field, value)
	for _, entry in ipairs(list) do
		if entry[field] == value then
			return entry
		end
	end
	return nil
end

function Util.FormatNumber(n)
	n = math.floor(n)
	if n < 1000 then
		return tostring(n)
	elseif n < 1000000 then
		return string.format("%.1fK", n / 1000)
	elseif n < 1000000000 then
		return string.format("%.2fM", n / 1000000)
	else
		return string.format("%.2fB", n / 1000000000)
	end
end

return Util
