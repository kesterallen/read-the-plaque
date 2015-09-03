/* Code based on Google Map APIv3 Tutorials */

var map;
var marker;

var def_zoomval = 2;
var def_lngval = 0.0;
var def_latval = -20.0;

function map_init() {
	var curpoint = new google.maps.LatLng(def_latval, def_lngval);

	map = new google.maps.Map(document.getElementById("mapitems"), {
		center: curpoint,
		zoom: def_zoomval,
        mapTypeId: google.maps.MapTypeId.ROADMAP
    });

	marker = new google.maps.Marker({map: map, position: curpoint});

	google.maps.event.addListener(map, 'click', function(event) {
		document.getElementById("plaque_location").value = event.latLng.lat() + ', ' + event.latLng.lng();
		marker.setPosition(event.latLng);
	});
} 
