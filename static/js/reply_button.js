function showReplyBox(vars){
    var reply_box = document.getElementById(vars);
    if ( reply_box.style.display == 'none' ){
    //If the div is hidden, show it
    reply_box.style.display = 'block';
  } else {
    //If the div is shown, hide it
    reply_box.style.display = 'none';
  }
}