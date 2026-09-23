import 'dart:convert';
import 'package:http/http.dart' as http;

class PognaliApi {
  final String baseUrl;
  final String? token;
  const PognaliApi({required this.baseUrl, this.token});

  Map<String,String> get _headers => {
    'Content-Type':'application/json',
    if (token != null) 'Authorization':'Bearer $token',
  };

  Future<List<dynamic>> events() async {
    final r = await http.get(Uri.parse('$baseUrl/events'), headers: _headers);
    if (r.statusCode >= 400) throw Exception('GET /events ${r.statusCode}');
    return jsonDecode(r.body) as List<dynamic>;
  }

  Future<Map<String,dynamic>> event(String id) async {
    final r = await http.get(Uri.parse('$baseUrl/events/$id'), headers: _headers);
    if (r.statusCode >= 400) throw Exception('GET /events/$id ${r.statusCode}');
    return jsonDecode(r.body) as Map<String,dynamic>;
  }

  Future<void> join(String id) async {
    final r = await http.post(Uri.parse('$baseUrl/events/$id/join'), headers: _headers);
    if (r.statusCode >= 400) throw Exception('JOIN ${r.statusCode}: ${r.body}');
  }

  Future<void> leave(String id) async {
    final r = await http.post(Uri.parse('$baseUrl/events/$id/leave'), headers: _headers);
    if (r.statusCode >= 400) throw Exception('LEAVE ${r.statusCode}: ${r.body}');
  }

  Future<List<dynamic>> messages(String id) async {
    final r = await http.get(Uri.parse('$baseUrl/events/$id/messages'), headers: _headers);
    if (r.statusCode >= 400) throw Exception('MESSAGES ${r.statusCode}');
    return jsonDecode(r.body) as List<dynamic>;
  }

  Future<void> sendMessage(String id, String text) async {
    final r = await http.post(Uri.parse('$baseUrl/events/$id/messages'),
      headers: _headers, body: jsonEncode({'text': text}));
    if (r.statusCode >= 400) throw Exception('SEND ${r.statusCode}: ${r.body}');
  }
}
