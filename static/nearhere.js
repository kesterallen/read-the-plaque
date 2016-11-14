function find_near_here() {
  //$("#locationModal").modal();
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      found_location,
      no_location
    );
  } else {
    alert("Geolocation is not supported by this browser.");
  }
}

function found_location(position) {
  console.log(position);
  var lat = position.coords.latitude;
  var lng = position.coords.longitude;
  url = "/nearby/" + lat + "/" + lng;
  window.location.href = url;
}

function no_location(error) {
  switch(error.code) {
    case error.PERMISSION_DENIED:
      $("#failedLocationModal").modal();
      return;
    case error.POSITION_UNAVAILABLE:
      alert("Location information is unavailable.");
      break;
    case error.TIMEOUT:
      alert("Location: the request to get location timed out.");
      break;
    case error.UNKNOWN_ERROR:
      alert("Location: an unknown error occurred.");
      break;
  }
  window.location.href = "/geo";
}
