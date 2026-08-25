def values_match(
    wikibase_value: dict, existing_value: dict, property_datatype: str
) -> bool:
    """
    Compare the value we would send to Wikibase against a value already
    stored in a claim returned by wbgetentities (mainsnak.datavalue.value).
    Inputs:
    - wikibase_value: The value we intend to send to Wikibase.
    - existing_value: The value already stored in Wikibase.
    - property_datatype: The Wikibase datatype of the property.
    Returns:
    - True if the values match. False otherwise.
    """
    if property_datatype == "wikibase-item":
        return isinstance(existing_value, dict) and wikibase_value.get(
            "id"
        ) == existing_value.get("id")
    if property_datatype in ("string", "url", "external-id"):
        return wikibase_value == existing_value
    if property_datatype == "monolingualtext":
        return (
            isinstance(existing_value, dict)
            and wikibase_value.get("text") == existing_value.get("text")
            and wikibase_value.get("language") == existing_value.get("language")
        )
    if property_datatype == "quantity":
        return isinstance(existing_value, dict) and wikibase_value.get(
            "amount"
        ) == existing_value.get("amount")
    if property_datatype == "time":
        return (
            isinstance(existing_value, dict)
            and wikibase_value.get("time") == existing_value.get("time")
            and wikibase_value.get("precision") == existing_value.get("precision")
        )
    return False


def find_existing_claim_guid(
    claims_by_pid: dict,
    pid: str,
    wikibase_value: dict,
    property_datatype: str,
) -> str | None:
    """
    Return the GUID of a matching existing claim, or None.
    Inputs:
    - claims_by_pid: A dictionary mapping property IDs to lists of claims.
    - pid: The property ID of the claim to find.
    - wikibase_value: The value we intend to send to Wikibase.
    - property_datatype: The Wikibase datatype of the property.
    Returns:
    - The GUID of a matching existing claim if found, or None if not found.
    """
    for claim in claims_by_pid.get(pid, []):
        if claim.get("mainsnak", {}).get("snaktype") != "value":
            continue
        existing_value = claim["mainsnak"].get("datavalue", {}).get("value")
        if values_match(wikibase_value, existing_value, property_datatype):
            return claim["id"]
    return None
