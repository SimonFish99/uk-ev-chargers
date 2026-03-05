import json

with open("data/chargers.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Total chargers:", len(data))
print()

sample = data[0]

print("Keys in charger object:")
print(sample.keys())
print()

print("Address info fields:")
print(sample["AddressInfo"].keys())
print()

print("Example location:")
print("Title:", sample["AddressInfo"].get("Title"))
print("Town:", sample["AddressInfo"].get("Town"))
print("County:", sample["AddressInfo"].get("StateOrProvince"))
print("Latitude:", sample["AddressInfo"].get("Latitude"))
print("Longitude:", sample["AddressInfo"].get("Longitude"))