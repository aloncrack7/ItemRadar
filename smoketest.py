from google.cloud import aiplatform as aip
aip.init(project="itemradar-prod", location="us-central1")

ep = aip.MatchingEngineIndexEndpoint(
    "projects/itemradar-prod/locations/us-central1/indexEndpoints/689088126383030272"
)

resp = ep.find_neighbors(
    deployed_index_id="item_embeddings_deployed2",
    queries=[[0.0] * 768],
    num_neighbors=5
)

for nb in resp[0]:           # resp → List[List[MatchNeighbor]]
    print(nb.id, nb.distance)