
if [ "$#" -ne 1 ]
then
  echo "Usage: $0 image_url"
  exit 1
fi

key=$(< ../key.txt)
json="{ \"requests\": [ { \"features\": [ { \"type\": \"TEXT_DETECTION\" } ], \"image\": { \"source\": { \"imageUri\": \"$1\" } } } ] }"
curl -s -H "Content-Type: application/json" "https://vision.googleapis.com/v1/images:annotate?key=$key" --data "$json" | grep text | tail -1 | perl -lape 's/\\n/ \n/g;'
