function find_near_here() {
    if (navigator.geolocation) {
        $("#locationModal").modal();
        navigator.geolocation.getCurrentPosition(function (position) {
            var lat = position.coords.latitude;
            var lng = position.coords.longitude;
            url = "/geo/" + lat + "/" + lng + "/8000"; // ~ 5 miles
            window.location.href = url;
        });
    } else { 
        alert("Geolocation is not supported by this browser.");
    }
}
