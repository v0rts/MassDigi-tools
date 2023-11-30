#!/usr/bin/env python3

# Create stub records in Arches
# Script adapted from Getty-provided ingest script

import requests
from typing import Final
from pydantic import BaseModel
# from typing import Tuple
import json
import uuid
import sys

import settings_arches as settings
import archesapiclient

# MySQL
import pymysql

import settings


"""
The Graph in arches is as explained here https://arches.readthedocs.io/en/7.2/data-model/?highlight=graph#graph-definition
a data model respenting top level objects like Visual Works, Physical Objects etc.
The id is autocreated from arches when creating the model and doesn't change, unless the Model represented by this graph,
gets deleted and re-created.
"""

GRAPH_ID: Final[str] = settings.graph_id
ARCHES_ENDPOINT: str = settings.arches_api

RESOURCES_ENDPOINT: Final[str] = f"{ARCHES_ENDPOINT}/resources"
RESOURCE_URL: Final[str] = f"{ARCHES_ENDPOINT}/resource"



url = ARCHES_ENDPOINT
client_id = settings.arches_api_clientid
username = settings.arches_api_username
password = settings.arches_api_password

a_client = archesapiclient.ArchesClient(url, client_id, username, password)



# Connect to db
try:
    conn = pymysql.connect(host=settings.host,
                           user=settings.user,
                           password=settings.password,
                           database=settings.database,
                           port=settings.port,
                           charset='utf8mb4',
                           autocommit=True,
                           cursorclass=pymysql.cursors.DictCursor)
    cur = conn.cursor()
except pymysql.Error as e:
    print(e)
    sys.exit(1)


# Run query
# query = ("with data as (SELECT id1_value as refid, id2_value as hmo FROM dpo_osprey.jpc_massdigi_ids where id_relationship = 'refid_hmo') "
#             " select d.*, j.unit_title, j.archive_box, j.archive_folder "
#             " from data d, jpc_aspace_data j where d.refid=j.refid")
query = ("""
            with data as (SELECT id1_value as refid, id2_value as hmo FROM dpo_osprey.jpc_massdigi_ids 
					where id_relationship = 'refid_hmo') 
             select d.*, 
             concat(j.unit_title, ' - Box ', j.archive_box, ' Folder ', j.archive_folder, ' Image ', 
             		LPAD(	
             		row_number() over (partition by refid order by d.refid, hmo),
             		4, '0')
             			) as unit_title, 
             j.archive_box, j.archive_folder 
             from data d, jpc_aspace_data j where d.refid=j.refid
             order by unit_title
             """)

cur.execute(query)

data = cur.fetchall()

query_insert = ("INSERT INTO jpc_massdigi_ids (id_relationship, id1_value, id2_value) "
           "VALUES ('hmo_arches', %(hmo)s, %(arches)s)")


for row in data:
    # Get HMO ID from database
    hmo_id = row['hmo']

    # Get filename from db to get sequence
    cur.execute("SELECT id2_value from jpc_massdigi_ids WHERE id1_value = %(hmo_id)s", {'hmo_id': hmo_id})

    res = cur.fetchall()   

    # Convert id
    id = "https://data.jpcarchive.org/{}".format(hmo_id)

    # # TO EXPAND
    # Get title, box, and folder of HMO from folder title in database
    # Example:
    #   title = "3T"
    #   box_no = "BI-001A"
    #   folder_no = "001"
    title = row['unit_title']
    folder_no = row['archive_folder']
    box_no = row['archive_box']
    sequence = #################
    
    if box_no != "":
        title = "{} - Box {}".format(title, box_no)
    
    if folder_no != "":
        title = "{} Folder {}".format(title, folder_no)

    # Read data model from file
    f = open('jpc_data_model4.json')
    json_data_model = json.load(f)
    f.close()

    # Replace values of TITLE
    json_data_model['_label'] = title
    json_data_model['identified_by'][0]['content'] = title

    resource_id = uuid.uuid3(uuid.NAMESPACE_URL, id)
    #json_data_model['id'] = f"urn:uuid:{resource_id}"
    json_data_model['id'] = f"https://data.jpcarchive.org/object/{resource_id}"
    json_data_model['identified_by'][0]['id'] = f"https://data.jpcarchive.org/object/{resource_id}/name/1"

    response = requests.put(
        f"{RESOURCES_ENDPOINT}/{GRAPH_ID}/{resource_id}",
        data=json.dumps(json_data_model),
        params=(("format", "json-ld"), ("indent", 4)),
        headers={"Authorization": f"Bearer {a.access_token}"},
    )

    print(response.status_code)

    cur.execute(query_insert, {'hmo': hmo_id, 'arches': str(resource_id)})


cur.close()
conn.close()
