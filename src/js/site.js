// Worksheet-sample carousel: the arrows scroll the track one slide at a time.
document.querySelectorAll('.carousel').forEach(function (c) {
  var track = c.querySelector('.track');
  var step = function () { var s = track.querySelector('.slide'); return s ? s.getBoundingClientRect().width + 20 : 300; };
  var prev = c.querySelector('.prev'), next = c.querySelector('.next');
  if (prev) prev.addEventListener('click', function () { track.scrollBy({ left: -step(), behavior: 'smooth' }); });
  if (next) next.addEventListener('click', function () { track.scrollBy({ left: step(), behavior: 'smooth' }); });
});
